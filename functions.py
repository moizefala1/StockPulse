from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import requests
import pandas_market_calendars as mcal
import time as _time

from params import (
    log, WEBHOOK, MARKET_TZ, MARKET_OPEN, MARKET_CLOSE, MARKET_DAYS,
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL, EMA_SHORT, EMA_LONG,
    BB_PERIOD, BB_STD, DATA_INTERVAL, DATA_PERIOD, MIN_CANDLES,
    BUY_THRESHOLD, SELL_THRESHOLD, TRADING_MODE,
)

#market time calculation
def market_is_open() -> bool:
    nyse = mcal.get_calendar("NYSE")
    now_et = datetime.now(MARKET_TZ)
    schedule = nyse.schedule(
        start_date=now_et.date(),
        end_date=now_et.date()
    )
    if schedule.empty:          # feriado o fin de semana
        return False
    open_t  = schedule.iloc[0]["market_open"].to_pydatetime()
    close_t = schedule.iloc[0]["market_close"].to_pydatetime()
    return open_t <= now_et <= close_t


def seconds_until_open() -> float:
    nyse   = mcal.get_calendar("NYSE")
    now_et = datetime.now(MARKET_TZ)
    for i in range(10):
        candidate_date = (now_et + timedelta(days=i)).date()
        schedule = nyse.schedule(start_date=candidate_date, end_date=candidate_date)
        if schedule.empty:
            continue
        open_t = schedule.iloc[0]["market_open"].to_pydatetime()
        if open_t > now_et:
            return max((open_t - now_et).total_seconds(), 60)
    return 3600


#discord notification
def send_discord(message: str, color: int = 0x4f98a3) -> None:
    if not WEBHOOK:
        log.info(f"[DISCORD] {message}")
        return

    content = ""
    if "@everyone" in message:
        content = "@everyone"
        message = message.replace("@everyone\n", "").replace("@everyone", "")

    if TRADING_MODE == "swing":
        mode_label = "Swing"
    elif TRADING_MODE == "crypto":
        mode_label = "Crypto"
    else:
        mode_label = "Intraday"
        
    payload = {
        "content": content,
        "embeds": [{
            "title": f"StockPulse · {mode_label}",
            "description": message.strip(),
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
        }]
    }
    try:
        requests.post(WEBHOOK, json=payload, timeout=5)
    except Exception as e:
        log.warning(f"Discord webhook fallo: {e}")


#if spy is bullish then its likely to be a bull market, anyways is recomandable that you check the calculations
#on the logs to make a final decision
def market_is_bullish() -> bool:
    try:
        df = yf.Ticker("SPY").history(period="3mo", interval="1d", auto_adjust=True)
        if len(df) < 50:
            return True
        close = df["Close"]
        ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
        precio = close.iloc[-1]
        alcista = precio > ema50
        log.info(f"SPY ${precio:.2f} vs EMA50 ${ema50:.2f} -> {'ALCISTA' if alcista else 'BAJISTA'}")
        return alcista
    except Exception as e:
        log.warning(f"No se pudo verificar tendencia SPY: {e}")
        return True


#retrieve data from yfinance
def get_data(symbol: str) -> pd.DataFrame | None:
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=DATA_PERIOD, interval=DATA_INTERVAL, auto_adjust=True)
        if df.empty or len(df) < MIN_CANDLES:
            log.warning(f"{symbol}: datos insuficientes ({len(df)} velas)")
            return None
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns={"stock splits": "splits"})
        return df
    except Exception as e:
        log.error(f"Error descargando {symbol}: {e}")
        return None
    
#retrive data from buda api (crypto mode)    
def get_data_crypto(symbol: str) -> pd.DataFrame | None:
    try:
        resolution = DATA_INTERVAL
        to_ts = int(_time.time())
        from_ts = to_ts - 7 * 24 * 60 * 60
        url = (
            f"https://www.buda.com/api/v2/tv/history"
            f"?symbol={symbol}&from={from_ts}&to={to_ts}&resolution={resolution}"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("s") != "ok":
            log.warning(f"{symbol}: buda respondio status={data.get('s')}")
            return None

        df = pd.DataFrame({
            "open":   data["o"],
            "high":   data["h"],
            "low":    data["l"],
            "close":  data["c"],
            "volume": data["v"],
        }, index=pd.to_datetime(data["t"], unit="s", utc=True))

        if len(df) < MIN_CANDLES:
            log.warning(f"{symbol}: datos insuficientes ({len(df)} velas)")
            return None

        return df
    except Exception as e:
        log.error(f"Error descargando crypto {symbol}: {e}")
        return None


#calculate the indicators from the data recieved (stored on a dataframe)
def get_indicators(df: pd.DataFrame) -> dict:
    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    vol   = df["volume"]

    rsi = ta.rsi(close, length=RSI_PERIOD)
    #MACD
    macd_df     = ta.macd(close, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
    macd_line   = macd_df[f"MACD_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}"]
    macd_signal = macd_df[f"MACDs_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}"]
    macd_hist   = macd_df[f"MACDh_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}"]

    #EMA
    ema_short = ta.ema(close, length=EMA_SHORT)
    ema_long  = ta.ema(close, length=EMA_LONG)

    #Bollinger Bands
    bb       = ta.bbands(close, length=BB_PERIOD, std=BB_STD)
    bb_lower = bb[[c for c in bb.columns if c.startswith("BBL_")]].iloc[:, 0]
    bb_mid   = bb[[c for c in bb.columns if c.startswith("BBM_")]].iloc[:, 0]
    bb_upper = bb[[c for c in bb.columns if c.startswith("BBU_")]].iloc[:, 0]

    #ATR
    atr       = ta.atr(high, low, close, length=14)
    vol_avg   = vol.rolling(20).mean()
    vol_ratio = (vol / vol_avg).iloc[-1]

    #StochRSI
    #if swing then use K and D to detect bull/bear crosses, otherwise use RSI
    stoch_rsi = ta.stochrsi(close, length=14)
    stoch_k   = stoch_rsi["STOCHRSIk_14_14_3_3"].iloc[-1] if stoch_rsi is not None else 50.0
    stoch_d   = stoch_rsi["STOCHRSId_14_14_3_3"].iloc[-1] if stoch_rsi is not None else 50.0
    stoch_k_prev = stoch_rsi["STOCHRSIk_14_14_3_3"].iloc[-2] if stoch_rsi is not None else 50.0
    stoch_d_prev = stoch_rsi["STOCHRSId_14_14_3_3"].iloc[-2] if stoch_rsi is not None else 50.0

    #ADX
    #only used in swing to filter out the lateral market
    adx_df = ta.adx(high, low, close, length=14)
    adx    = float(adx_df["ADX_14"].iloc[-1]) if adx_df is not None else 25.0

    return {
        "price":          float(close.iloc[-1]),
        "rsi":            float(rsi.iloc[-1]),
        "stoch_k":        float(stoch_k),
        "stoch_d":        float(stoch_d),
        "stoch_k_prev":   float(stoch_k_prev),
        "stoch_d_prev":   float(stoch_d_prev),
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
        "adx":            adx,
    }


#signal main function

def get_signal(ind: dict, bullish_market: bool = True) -> tuple[str, list[str]]:
    if TRADING_MODE == "swing":
        return _get_signal_swing(ind, bullish_market)
    return _get_signal_intraday(ind)


#intraday signals are more reactive and have lower thresholds to capture more opportunities,
#while swing signals are more conservative and give more weight to trend confirmation 
#indicators like ADX and StochRSI crossovers
def _get_signal_intraday(ind: dict) -> tuple[str, list[str]]:
    buy_score  = 0
    sell_score = 0
    reasons    = []

    if 35 <= ind["rsi"] <= 58:
        buy_score += 1
        reasons.append(f"RSI neutral/comprable ({ind['rsi']:.1f})")
    if ind["rsi"] > 68:
        sell_score += 1
        reasons.append(f"RSI sobrecomprado ({ind['rsi']:.1f})")
    if ind["rsi"] < 32:
        sell_score += 1
        reasons.append(f"RSI sobrevendido ({ind['rsi']:.1f})")

    if ind["macd_hist"] > 0 and ind["macd_hist_prev"] <= 0:
        buy_score += 2
        reasons.append("MACD cruce alcista")
    if ind["macd_hist"] < 0 and ind["macd_hist_prev"] >= 0:
        sell_score += 2
        reasons.append("MACD cruce bajista")

    if ind["price"] > ind["ema_short"] > ind["ema_long"]:
        buy_score += 1
        reasons.append("Precio > EMA20 > EMA50")
    if ind["price"] < ind["ema_short"]:
        sell_score += 1
        reasons.append("Precio < EMA20")

    if ind["price"] <= ind["bb_mid"]:
        buy_score += 1
        reasons.append("Precio en mitad inferior de BB")
    if ind["price"] >= ind["bb_upper"] * 0.98:
        sell_score += 1
        reasons.append("Precio tocando banda superior BB")

    if ind["vol_ratio"] > 1.2:
        buy_score += 1
        reasons.append(f"Volumen elevado ({ind['vol_ratio']:.1f}x promedio)")

    if ind["stoch_k"] < 25:
        buy_score += 1
        reasons.append(f"Stoch RSI bajo ({ind['stoch_k']:.1f})")
    if ind["stoch_k"] > 80:
        sell_score += 1
        reasons.append(f"Stoch RSI alto ({ind['stoch_k']:.1f})")

    if buy_score >= BUY_THRESHOLD:
        return "BUY", reasons
    if sell_score >= SELL_THRESHOLD:
        return "SELL", reasons
    return "HOLD", reasons

def _get_signal_swing(ind: dict, bullish_market: bool) -> tuple[str, list[str]]:
    buy_score  = 0
    sell_score = 0
    reasons    = []

    if ind["adx"] < 20:
        reasons.append(f"ADX bajo ({ind['adx']:.1f}) — mercado lateral, sin señal")
        return "HOLD", reasons
    reasons.append(f"ADX {ind['adx']:.1f} — tendencia activa")
    #RSI
    if ind["rsi"] <= 40:
        buy_score += 1
        reasons.append(f"RSI en sobreventa ({ind['rsi']:.1f})")
    if ind["rsi"] > 68:
        sell_score += 1
        reasons.append(f"RSI sobrecomprado ({ind['rsi']:.1f})")
    if ind["rsi"] < 25:
        sell_score += 2 #the threshold is adjusted to better capture swing opportunities
        reasons.append(f"RSI en panico extremo ({ind['rsi']:.1f})")
    #MACD
    if ind["macd_hist"] > 0 and ind["macd_hist_prev"] <= 0:
        buy_score += 2
        reasons.append("MACD cruce alcista")
    if ind["macd_hist"] < 0 and ind["macd_hist_prev"] >= 0:
        sell_score += 2
        reasons.append("MACD cruce bajista")

    #EMA
    if ind["price"] > ind["ema_short"] > ind["ema_long"]:
        buy_score += 1
        reasons.append("Precio > EMA20 > EMA50")
    if ind["price"] < ind["ema_short"]:
        sell_score += 1
        reasons.append("Precio < EMA20")

    #Bollinger Bands
    if ind["price"] <= ind["bb_mid"]:
        buy_score += 1
        reasons.append("Precio en mitad inferior de BB")
    if ind["price"] >= ind["bb_upper"] * 0.98:
        sell_score += 1
        reasons.append("Precio tocando banda superior BB")

    #Volumen
    vol_confirm = ind["vol_ratio"] > 1.2
    if vol_confirm:
        reasons.append(f"Volumen confirma ({ind['vol_ratio']:.1f}x promedio)")

    #StochRSI
    k, d, kp, dp = ind["stoch_k"], ind["stoch_d"], ind["stoch_k_prev"], ind["stoch_d_prev"]
    stoch_bull_cross = k > d and kp <= dp and k < 40   #cruce alcista desde zona baja
    stoch_bear_cross = k < d and kp >= dp and k > 60   #cruce bajista desde zona alta
    
    if stoch_bull_cross:
        score = 2 if vol_confirm else 1  
        buy_score += score
        reasons.append(f"StochRSI cruce alcista K({k:.1f}) > D({d:.1f}) desde sobreventa{' + volumen' if vol_confirm else ''}")
    if stoch_bear_cross:
        score = 2 if vol_confirm else 1
        sell_score += score
        reasons.append(f"StochRSI cruce bajista K({k:.1f}) < D({d:.1f}) desde sobrecompra{' + volumen' if vol_confirm else ''}")

    #macro filter
    if not bullish_market and buy_score >= BUY_THRESHOLD:
        reasons.append("BUY bloqueado — SPY bajo EMA50 (mercado bajista)")
        return "HOLD", reasons

    if buy_score >= BUY_THRESHOLD:
        return "BUY", reasons
    if sell_score >= SELL_THRESHOLD:
        return "SELL", reasons
    return "HOLD", reasons
