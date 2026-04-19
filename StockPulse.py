import time
from datetime import datetime
from params import log, SYMBOLS, CRYPTO_SYMBOLS, MARKET_TZ, TRADING_MODE, SCAN_INTERVAL, SCAN_HOUR_ET, SCAN_MINUTE_ET
from functions import (
    market_is_open, seconds_until_open, send_discord,
    get_data, get_data_crypto, get_indicators, get_signal, market_is_bullish, crypto_is_bullish,
)

def run_cycle() -> None:
    log.info("=" * 60)
    log.info(f"Ciclo [{TRADING_MODE.upper()}] — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    alerts = []

    if TRADING_MODE == "swing":
        bullish = market_is_bullish()
        if not bullish:
            send_discord(
                "**Filtro macro activo** — SPY bajo EMA50 diaria.\n"
                "Señales BUY bloqueadas. Solo se reportarán señales SELL.",
                0xbb653b,
            )
    elif TRADING_MODE == "crypto":
        bullish = crypto_is_bullish()
        if not bullish:
            send_discord(
                "**Filtro macro activo** — BTC bajo EMA50 4h.\n"
                "Señales BUY bloqueadas. Solo se reportarán señales SELL.",
                0xbb653b,
            )
    else:
        bullish = True

    symbols = CRYPTO_SYMBOLS if TRADING_MODE == "crypto" else SYMBOLS
    fetch_fn = get_data_crypto if TRADING_MODE == "crypto" else get_data

    for symbol in symbols:
        df = fetch_fn(symbol)
        if df is None:
            continue
        try:
            ind = get_indicators(df)
            signal, reasons = get_signal(ind, bullish_market=bullish)

            log.info(
                f"{symbol:6s} | ${ind['price']:>10.2f} USD | RSI: {ind['rsi']:>5.1f} | "
                f"MACD_h: {ind['macd_hist']:>7.4f} | EMA20: {ind['ema_short']:>10.2f} | {signal}"
            )

            if signal in ("BUY", "SELL"):
                emoji = "🟢" if signal == "BUY" else "🔴"
                if TRADING_MODE == "crypto":
                    try:
                        import yfinance as yf
                        fx = yf.Ticker("CLP=X").history(period="1d", interval="1h", auto_adjust=True)
                        usd_clp = float(fx["Close"].iloc[-1])
                        price_clp = ind["price"] * usd_clp
                        price_str = f"`${ind['price']:.2f} USD` (~`${price_clp:,.0f} CLP`)"
                    except Exception:
                        price_str = f"`${ind['price']:.2f} USD`"
                else:
                    price_str = f"`${ind['price']:.2f}`"

                msg = (
                    f"@everyone\n"
                    f"{emoji} **{signal} {symbol}** — {price_str}\n"
                    f"RSI: `{ind['rsi']:.1f}` | Stoch K: `{ind['stoch_k']:.1f}`\n"
                    f"MACD hist: `{ind['macd_hist']:.4f}` (prev `{ind['macd_hist_prev']:.4f}`)\n"
                    f"EMA20: `{ind['ema_short']:.2f}` / EMA50: `{ind['ema_long']:.2f}`\n"
                    f"BB upper: `{ind['bb_upper']:.2f}` | BB mid: `{ind['bb_mid']:.2f}`\n"
                    f"Vol ratio: `{ind['vol_ratio']:.2f}x` | ATR: `{ind['atr']:.2f}`\n"
                    f"**Razones:** {', '.join(reasons)}"
                )

                color = 0x6daa45 if signal == "BUY" else 0xdd6974
                send_discord(msg, color)
                alerts.append(f"{signal} {symbol}")

        except Exception as e:
            log.error(f"Error procesando {symbol}: {e}")

    if not alerts:
        log.info("Sin señales esta ronda.")
    else:
        log.info(f"Alertas enviadas: {', '.join(alerts)}")

def run_intraday() -> None:
    log.info("Modo: INTRADAY — escaneo cada 30 min")
    send_discord(
        f"@everyone\nStockPulse iniciado · Modo **INTRADAY**\n"
        f"Parrilla: {', '.join(SYMBOLS)}",
        0x4f98a3,
    )
    while True:
        if market_is_open():
            try:
                run_cycle()
            except Exception as e:
                log.error(f"Error inesperado: {e}")
                send_discord(f"Error en ciclo: `{e}`", 0xbb653b)
            log.info(f"Esperando {SCAN_INTERVAL // 60} minutos...")
            time.sleep(SCAN_INTERVAL)
        else:
            wait = seconds_until_open()
            now_et = datetime.now(MARKET_TZ)
            log.info(
                f"Mercado cerrado ({now_et.strftime('%A %H:%M ET')}). "
                f"Proxima apertura en {wait/3600:.1f}h."
            )
            time.sleep(min(wait, 300))

def run_swing() -> None:
    log.info("Modo: SWING — escaneo diario a las 09:35 ET")
    send_discord(
        f"@everyone\nStockPulse iniciado · Modo **SWING**\n"
        f"Escaneo diario a las 09:35 ET\nParrilla: {', '.join(SYMBOLS)}",
        0x4f98a3,
    )
    last_scan_date = None
    while True:
        now_et = datetime.now(MARKET_TZ)
        today = now_et.date()
        is_market_day = now_et.weekday() in {0, 1, 2, 3, 4}
        after_935 = (now_et.hour, now_et.minute) >= (SCAN_HOUR_ET, SCAN_MINUTE_ET)
        not_yet_scanned = last_scan_date != today
        if is_market_day and after_935 and not_yet_scanned:
            try:
                run_cycle()
            except Exception as e:
                log.error(f"Error inesperado: {e}")
                send_discord(f"Error en ciclo swing: `{e}`", 0xbb653b)
            last_scan_date = today
            log.info("Escaneo diario completado. Proximo escaneo mañana a las 09:35 ET.")
        time.sleep(60)

def run_crypto() -> None:
    log.info("Modo: CRYPTO — escaneo cada 30 min (24/7)")
    send_discord(
        f"@everyone\nStockPulse iniciado · Modo **CRYPTO**\n"
        f"Parrilla: {', '.join(CRYPTO_SYMBOLS)}",
        0x4f98a3,
    )
    while True:
        try:
            run_cycle()
        except Exception as e:
            log.error(f"Error inesperado: {e}")
            send_discord(f"Error en ciclo crypto: `{e}`", 0xbb653b)
        log.info(f"Esperando {SCAN_INTERVAL // 60} minutos...")
        time.sleep(SCAN_INTERVAL)

def main() -> None:
    log.info(f"Iniciando StockPulse — TRADING_MODE={TRADING_MODE.upper()}")
    if TRADING_MODE == "crypto":
        log.info(f"Parrilla: {', '.join(CRYPTO_SYMBOLS)}")
        run_crypto()
    elif TRADING_MODE == "intraday":
        log.info(f"Parrilla: {', '.join(SYMBOLS)}")
        run_intraday()
    else:
        log.info(f"Parrilla: {', '.join(SYMBOLS)}")
        run_swing()

if __name__ == "__main__":
    main()
