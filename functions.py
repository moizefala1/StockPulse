from datetime import datetime
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import requests

from params import (
    log, WEBHOOK, MARKET_TZ, MARKET_OPEN, MARKET_CLOSE, MARKET_DAYS,
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL, EMA_SHORT, EMA_LONG,
    BB_PERIOD, BB_STD
)


#market verifications
def market_is_open() -> bool:
    now_et = datetime.now(MARKET_TZ)
    if now_et.weekday() not in MARKET_DAYS:
        return False
    t = now_et.time()
    return MARKET_OPEN <= t < MARKET_CLOSE

def seconds_until_open() -> float:
    now_et = datetime.now(MARKET_TZ)
    check = now_et
    while True:
        if check.weekday() in MARKET_DAYS:
            candidate = check.replace(
                hour=MARKET_OPEN.hour, minute=MARKET_OPEN.minute, second=0, microsecond=0
            )
            if candidate > now_et:
                delta = (candidate - now_et).total_seconds()
                return max(delta, 60)
        check = check.replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        check += timedelta(days=1)


#discord function
def send_discord(message: str, color: int = 0x4f98a3) -> None:
    if not WEBHOOK:
        log.info(f"[DISCORD] {message}")
        return
    payload = {
        "embeds": [{
            "title": "📈 StockPulse",
            "description": message,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
        }]
    }
    try:
        requests.post(WEBHOOK, json=payload, timeout=5)
    except Exception as e:
        log.warning(f"Discord webhook falló: {e}")


#indicators
def get_data(symbol: str) -> pd.DataFrame | None:
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", interval="30m")
        if df.empty or len(df) < 60:
            log.warning(f"{symbol}: datos insuficientes ({len(df)} velas)")
            return None
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns={"stock splits": "splits"})
        return df
    except Exception as e:
        log.error(f"Error descargando {symbol}: {e}")
        return None


def get_indicators(df: pd.DataFrame) -> dict:
    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    vol   = df["volume"]

    rsi = ta.rsi(close, length=RSI_PERIOD)

    macd_df = ta.macd(close, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
    macd_line   = macd_df[f"MACD_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}"]
    macd_signal = macd_df[f"MACDs_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}"]
    macd_hist   = macd_df[f"MACDh_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}"]

    ema_short = ta.ema(close, length=EMA_SHORT)
    ema_long  = ta.ema(close, length=EMA_LONG)

    bb = ta.bbands(close, length=BB_PERIOD, std=BB_STD)
    bb_upper = bb[f"BBU_{BB_PERIOD}_{float(BB_STD)}"]
    bb_lower = bb[f"BBL_{BB_PERIOD}_{float(BB_STD)}"]
    bb_mid   = bb[f"BBM_{BB_PERIOD}_{float(BB_STD)}"]

    atr = ta.atr(high, low, close, length=14)
    vol_avg   = vol.rolling(20).mean()
    vol_ratio = (vol / vol_avg).iloc[-1]

    stoch_rsi = ta.stochrsi(close, length=14)
    stoch_k = stoch_rsi["STOCHRSIk_14_14_3_3"].iloc[-1] if stoch_rsi is not None else 50.0

    return {
        "price":          float(close.iloc[-1]),
        "rsi":            float(rsi.iloc[-1]),
        "stoch_k":        float(stoch_k),
        "macd":           float(macd_line.iloc[-1]),
        "macd_signal":    float(macd_signal.iloc[-1]),
        "macd_hist":      float(macd_hist.iloc[-1]),
        "macd_hist_prev": float(macd_hist.iloc[-2]),
        "ema_short":      float(ema_short.iloc[-1]),
        "ema_long":       float(ema_long.iloc[-1]),
        "bb_upper":       float(bb_upper.iloc[-1]),
        "bb_lower":       float(bb_lower.iloc[-1]),
        "bb_mid":         float(bb_mid.iloc[-1]),
        "atr":            float(atr.iloc[-1]),
        "vol_ratio":      float(vol_ratio),
    }


#signal generation
def get_signal(ind: dict) -> tuple[str, list[str]]:
    buy_score  = 0
    sell_score = 0
    reasons    = []

    #RSI
    if 35 <= ind["rsi"] <= 58:
        buy_score += 1
        reasons.append(f"RSI neutral/comprable ({ind['rsi']:.1f})")
    if ind["rsi"] > 68:
        sell_score += 1
        reasons.append(f"RSI sobrecomprado ({ind['rsi']:.1f})")
    if ind["rsi"] < 32:
        sell_score += 1
        reasons.append(f"RSI sobrevendido — posible rebote o pánico ({ind['rsi']:.1f})")

    #MACD datacross-referencing
    if ind["macd_hist"] > 0 and ind["macd_hist_prev"] <= 0:
        buy_score += 2
        reasons.append("MACD cruce alcista ✅")
    if ind["macd_hist"] < 0 and ind["macd_hist_prev"] >= 0:
        sell_score += 2
        reasons.append("MACD cruce bajista ❌")



    #EMA tendency
    if ind["price"] > ind["ema_short"] > ind["ema_long"]:
        buy_score += 1
        reasons.append("Precio > EMA20 > EMA50")
    if ind["price"] < ind["ema_short"]:
        sell_score += 1
        reasons.append("Precio < EMA20")

    #Bollinger
    if ind["price"] <= ind["bb_mid"]:
        buy_score += 1
        reasons.append("Precio en mitad inferior de BB")
    if ind["price"] >= ind["bb_upper"] * 0.98:
        sell_score += 1
        reasons.append("Precio tocando banda superior BB")

    #volume
    if ind["vol_ratio"] > 1.2:
        buy_score += 1
        reasons.append(f"Volumen elevado ({ind['vol_ratio']:.1f}x promedio)")

    #stochastic RSI
    if ind["stoch_k"] < 25:
        buy_score += 1
        reasons.append(f"Stoch RSI bajo ({ind['stoch_k']:.1f})")
    if ind["stoch_k"] > 80:
        sell_score += 1
        reasons.append(f"Stoch RSI alto ({ind['stoch_k']:.1f})")

    #return signal and reasons
    if buy_score >= 4:
        return "BUY", reasons
    if sell_score >= 3:
        return "SELL", reasons
    return "HOLD", reasons
