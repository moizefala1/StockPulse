import argparse
import signal

from params import init

init()

import time  # noqa: E402
from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: E402
from datetime import datetime  # noqa: E402
import yfinance as yf  # noqa: E402
from params import (  # noqa: E402
    log,
    SYMBOLS,
    CRYPTO_SYMBOLS,
    MARKET_TZ,
    TRADING_MODE,
    SCAN_INTERVAL,
    SCAN_HOUR_ET,
    SCAN_MINUTE_ET,
)
from functions import (  # noqa: E402
    market_is_open,
    seconds_until_open,
    send_discord,
    get_data,
    get_data_crypto,
    get_indicators,
    get_signal,
    market_is_bullish,
    crypto_is_bullish,
)
from simulator import get_portfolio  # noqa: E402


def _process_symbol(symbol, fetch_fn, bullish):
    df = fetch_fn(symbol)
    if df is None:
        return (symbol, None, None, [])
    try:
        ind = get_indicators(df)
        signal, reasons = get_signal(ind, bullish_market=bullish)
        return (symbol, signal, ind, reasons)
    except Exception as e:
        log.error(f"Error procesando {symbol}: {e}")
        return (symbol, None, None, [])


_shutdown_requested = False


def _handle_shutdown(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    log.info("Senal de apagado recibida. Cerrando posiciones...")


def run_cycle(portfolio=None) -> None:
    log.info("=" * 60)
    log.info(
        f"Ciclo [{TRADING_MODE.upper()}] — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    alerts = []

    if TRADING_MODE == "swing":
        bullish = market_is_bullish()
        if not bullish:
            send_discord(
                "**Filtro macro activo** — SPY bajo EMA50 diaria.\n"
                "Señales BUY bloqueadas. Solo se reportarán señales SELL.",
                0xBB653B,
            )
    elif TRADING_MODE == "crypto":
        bullish = crypto_is_bullish()
        if not bullish:
            send_discord(
                "**Filtro macro activo** — BTC bajo EMA50 4h.\n"
                "Señales BUY bloqueadas. Solo se reportarán señales SELL.",
                0xBB653B,
            )
    else:
        bullish = True

    symbols = CRYPTO_SYMBOLS if TRADING_MODE == "crypto" else SYMBOLS
    fetch_fn = get_data_crypto if TRADING_MODE == "crypto" else get_data

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_process_symbol, s, fetch_fn, bullish): s for s in symbols
        }
        for future in as_completed(futures):
            symbol, signal, ind, reasons = future.result()
            if signal is None:
                continue
            results.append((symbol, signal, ind, reasons))

    results.sort(key=lambda r: r[0])

    for symbol, signal, ind, reasons in results:
        log.info(
            f"{symbol:6s} | ${ind['price']:>10.2f} USD | RSI: {ind['rsi']:>5.1f} | "
            f"MACD_h: {ind['macd_hist']:>7.4f} | EMA20: {ind['ema_short']:>10.2f} | GAP: {ind.get('gap_pct', 0.0):>6.2f}% | {signal}"
        )

        if portfolio is not None:
            portfolio.update_price(symbol, ind["price"])

        if signal in ("BUY", "SELL"):
            if portfolio is not None:
                if signal == "BUY":
                    portfolio.on_buy(symbol, ind["price"])
                else:
                    portfolio.on_sell(symbol, ind["price"])
            emoji = "🟢" if signal == "BUY" else "🔴"
            if TRADING_MODE == "crypto":
                try:
                    fx = yf.Ticker("CLP=X").history(
                        period="1d", interval="1h", auto_adjust=True
                    )
                    usd_clp = float(fx["Close"].iloc[-1])
                    price_clp = ind["price"] * usd_clp
                    price_str = f"`${ind['price']:.2f} USD` (~`${price_clp:,.0f} CLP`)"
                except Exception:
                    log.warning("No se pudo obtener tasa CLP — mostrando solo USD")
                    price_str = f"`${ind['price']:.2f} USD`"
            else:
                price_str = f"`${ind['price']:.2f}`"

            msg = (
                f"@everyone\n"
                f"{emoji} **{signal} {symbol}** — {price_str}\n"
                f"RSI: `{ind['rsi']:.1f}` | Stoch K: `{ind['stoch_k']:.1f}`\n"
                f"MACD hist: `{ind['macd_hist']:.4f}` (prev `{ind['macd_hist_prev']:.4f}`)\n"
                f"EMA20: `{ind['ema_short']:.2f}` / EMA50: `{ind['ema_long']:.2f}`\n"
                f"Gap overnight: `{ind.get('gap_pct', 0.0):.2f}%` (open `{ind.get('open', ind['price']):.2f}` vs prev close `{ind.get('prev_close', ind['price']):.2f}`)\n"
                f"BB upper: `{ind['bb_upper']:.2f}` | BB mid: `{ind['bb_mid']:.2f}`\n"
                f"Vol ratio: `{ind['vol_ratio']:.2f}x` | ATR: `{ind['atr']:.2f}`\n"
                f"**Razones:** {', '.join(reasons)}"
            )

            color = 0x6DAA45 if signal == "BUY" else 0xDD6974
            send_discord(msg, color)
            alerts.append(f"{signal} {symbol}")

    if not alerts:
        log.info("Sin señales esta ronda.")
    else:
        log.info(f"Alertas enviadas: {', '.join(alerts)}")


def run_intraday(portfolio=None) -> None:
    log.info("Modo: INTRADAY — escaneo cada 30 min")
    send_discord(
        f"@everyone\nStockPulse iniciado · Modo **INTRADAY**\n"
        f"Parrilla: {', '.join(SYMBOLS)}",
        0x4F98A3,
    )
    while True:
        if _shutdown_requested:
            if portfolio is not None:
                portfolio.close_all()
                log.info(portfolio.summary())
            break
        if market_is_open():
            t0 = time.time()
            try:
                run_cycle(portfolio=portfolio)
            except Exception as e:
                log.error(f"Error inesperado: {e}")
                send_discord(f"Error en ciclo: `{e}`", 0xBB653B)
            elapsed = time.time() - t0
            wait = max(SCAN_INTERVAL - elapsed, 1)
            log.info(f"Esperando {wait // 60}m {wait % 60:.0f}s...")
            time.sleep(wait)
        else:
            wait = seconds_until_open()
            now_et = datetime.now(MARKET_TZ)
            log.info(
                f"Mercado cerrado ({now_et.strftime('%A %H:%M ET')}). "
                f"Proxima apertura en {wait / 3600:.1f}h."
            )
            time.sleep(min(wait, 300))


def run_swing(portfolio=None) -> None:
    log.info("Modo: SWING — escaneo diario a las 09:35 ET")
    send_discord(
        f"@everyone\nStockPulse iniciado · Modo **SWING**\n"
        f"Escaneo diario a las 09:35 ET\nParrilla: {', '.join(SYMBOLS)}",
        0x4F98A3,
    )
    last_scan_date = None
    while True:
        if _shutdown_requested:
            if portfolio is not None:
                portfolio.close_all()
                log.info(portfolio.summary())
            break
        now_et = datetime.now(MARKET_TZ)
        today = now_et.date()
        after_935 = (now_et.hour, now_et.minute) >= (SCAN_HOUR_ET, SCAN_MINUTE_ET)
        not_yet_scanned = last_scan_date != today
        if market_is_open() and after_935 and not_yet_scanned:
            try:
                run_cycle(portfolio=portfolio)
            except Exception as e:
                log.error(f"Error inesperado: {e}")
                send_discord(f"Error en ciclo swing: `{e}`", 0xBB653B)
            last_scan_date = today
            log.info(
                "Escaneo diario completado. Proximo escaneo proximo dia habil a las 09:35 ET."
            )
            time.sleep(60)
        else:
            if not after_935:
                if market_is_open():
                    target = now_et.replace(
                        hour=SCAN_HOUR_ET,
                        minute=SCAN_MINUTE_ET,
                        second=0,
                        microsecond=0,
                    )
                    wait = max((target - now_et).total_seconds(), 1)
                else:
                    wait = seconds_until_open()
                time.sleep(min(wait, 300))
            else:
                time.sleep(60)


def run_crypto(portfolio=None) -> None:
    log.info("Modo: CRYPTO — escaneo cada 30 min (24/7)")
    send_discord(
        f"@everyone\nStockPulse iniciado · Modo **CRYPTO**\n"
        f"Parrilla: {', '.join(CRYPTO_SYMBOLS)}",
        0x4F98A3,
    )
    while True:
        if _shutdown_requested:
            if portfolio is not None:
                portfolio.close_all()
                log.info(portfolio.summary())
            break
        t0 = time.time()
        try:
            run_cycle(portfolio=portfolio)
        except Exception as e:
            log.error(f"Error inesperado: {e}")
            send_discord(f"Error en ciclo crypto: `{e}`", 0xBB653B)
        elapsed = time.time() - t0
        wait = max(SCAN_INTERVAL - elapsed, 1)
        log.info(f"Esperando {wait // 60}m {wait % 60:.0f}s...")
        time.sleep(wait)


def main() -> None:
    parser = argparse.ArgumentParser(description="StockPulse — trading bot")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Mostrar resumen de la simulacion guardada y salir",
    )
    parser.add_argument(
        "--sim",
        action="store_true",
        default=False,
        help="Activar simulacion de paper trading ($150 iniciales)",
    )
    args = parser.parse_args()

    if args.summary:
        portfolio = get_portfolio()
        log.info(portfolio.summary())
        return

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    portfolio = get_portfolio() if args.sim else None
    if portfolio is not None:
        log.info(f"Simulacion activa — capital inicial: ${portfolio.initial_cash:.2f}")

    log.info(f"Iniciando StockPulse — TRADING_MODE={TRADING_MODE.upper()}")
    if TRADING_MODE == "crypto":
        log.info(f"Parrilla: {', '.join(CRYPTO_SYMBOLS)}")
        run_crypto(portfolio=portfolio)
    elif TRADING_MODE == "intraday":
        log.info(f"Parrilla: {', '.join(SYMBOLS)}")
        run_intraday(portfolio=portfolio)
    else:
        log.info(f"Parrilla: {', '.join(SYMBOLS)}")
        run_swing(portfolio=portfolio)


if __name__ == "__main__":
    main()
