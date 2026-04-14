import time
from datetime import datetime
from params import log, SYMBOLS, INTERVAL, MARKET_TZ
from functions import (
    market_is_open, seconds_until_open, send_discord, 
    get_data, get_indicators, get_signal
)

def run_cycle() -> None:
    log.info("=" * 60)
    log.info(f"Nuevo ciclo — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    alerts = []

    for symbol in SYMBOLS:
        df = get_data(symbol)
        if df is None:
            continue
        try:
            ind = get_indicators(df)
            signal, reasons = get_signal(ind)

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
                    f"Vol ratio: `{ind['vol_ratio']:.2f}x`\n"
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


def main() -> None:
    log.info("Iniciando Stocks Trading Bot...")
    log.info(f"Parrilla: {', '.join(SYMBOLS)}")
    send_discord(
        f"@everyone\n"
        f"✅ Stocks Bot iniciado — solo alertas Discord\nParrilla: {', '.join(SYMBOLS)}",
        0x4f98a3
    )

    while True:
        if market_is_open():
            try:
                run_cycle()
            except Exception as e:
                log.error(f"Error inesperado: {e}")
                send_discord(f"⚠️ Error en ciclo: `{e}`", 0xbb653b)
            log.info(f"Esperando {INTERVAL // 60} minutos...")
            time.sleep(INTERVAL)
        else:
            wait = seconds_until_open()
            now_et = datetime.now(MARKET_TZ)
            log.info(
                f"Mercado cerrado ({now_et.strftime('%A %H:%M ET')}). "
                f"Próxima apertura en {wait/3600:.1f}h."
            )
            #we sleep in blocks of 5 minutes to avoid blocking os signals like SIGTERM
            time.sleep(min(wait, 300))


if __name__ == "__main__":
    main()
