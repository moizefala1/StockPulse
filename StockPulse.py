import time
from datetime import datetime
from params import log, SYMBOLS, MARKET_TZ, TRADING_MODE, SCAN_INTERVAL, SCAN_HOUR_ET, SCAN_MINUTE_ET
from functions import (
    market_is_open, seconds_until_open, send_discord,
    get_data, get_indicators, get_signal, market_is_bullish,
)


def run_cycle() -> None:
    log.info("=" * 60)
    log.info(f"Ciclo [{TRADING_MODE.upper()}] — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    alerts = []

    bullish = market_is_bullish() if TRADING_MODE == "swing" else True
    if TRADING_MODE == "swing" and not bullish:
        send_discord(
            "**Filtro macro activo** — SPY bajo EMA50 diaria.\n"
            "Señales BUY bloqueadas. Solo se reportarán señales SELL.",
            0xbb653b,
        )

    for symbol in SYMBOLS:
        df = get_data(symbol)
        if df is None:
            continue
        try:
            ind = get_indicators(df)
            signal, reasons = get_signal(ind, bullish_market=bullish)

            log.info(
                f"{symbol:6s} | ${ind['price']:>8.2f} | RSI: {ind['rsi']:>5.1f} | "
                f"MACD_h: {ind['macd_hist']:>7.4f} | EMA20: {ind['ema_short']:>8.2f} | {signal}"
            )

            if signal in ("BUY", "SELL"):
                emoji = "🟢" if signal == "BUY" else "🔴"
                msg = (
                    f"@everyone\n"
                    f"{emoji} **{signal} {symbol}** — `${ind['price']:.2f}`\n"
                    f"RSI: `{ind['rsi']:.1f}` | Stoch K: `{ind['stoch_k']:.1f}`\n"
                    f"MACD hist: `{ind['macd_hist']:.4f}` (prev `{ind['macd_hist_prev']:.4f}`)\n"
                    f"EMA20: `{ind['ema_short']:.2f}` / EMA50: `{ind['ema_long']:.2f}`\n"
                    f"BB upper: `{ind['bb_upper']:.2f}` | BB mid: `{ind['bb_mid']:.2f}`\n"
                    f"Vol ratio: `{ind['vol_ratio']:.2f}x` | ATR: `{ind['atr']:.2f}`"
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
        today  = now_et.date()

        is_market_day   = now_et.weekday() in {0, 1, 2, 3, 4}
        after_935       = (now_et.hour, now_et.minute) >= (SCAN_HOUR_ET, SCAN_MINUTE_ET)
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


def main() -> None:
    log.info(f"Iniciando StockPulse — TRADING_MODE={TRADING_MODE.upper()}")
    log.info(f"Parrilla: {', '.join(SYMBOLS)}")
    if TRADING_MODE == "intraday":
        run_intraday()
    else:
        run_swing()


if __name__ == "__main__":
    main()
