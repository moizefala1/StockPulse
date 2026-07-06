"""Tests for signal functions in functions.py."""

from params import init

init()

from functions import (  # noqa: E402
    _get_signal_intraday,
    _get_signal_swing,
    _get_signal_crypto,
)


def _base_indicators(**overrides):
    """Return a complete indicator dict with sensible neutral defaults."""
    d = {
        "price": 100.0,
        "prev_close": 99.0,
        "open": 100.5,
        "gap_pct": 1.5,
        "rsi": 50.0,
        "stoch_k": 50.0,
        "stoch_d": 50.0,
        "stoch_k_prev": 50.0,
        "stoch_d_prev": 50.0,
        "macd": 0.0,
        "macd_signal": 0.0,
        "macd_hist": 0.01,
        "macd_hist_prev": -0.01,
        "ema_short": 95.0,
        "ema_long": 90.0,
        "bb_upper": 110.0,
        "bb_lower": 80.0,
        "bb_mid": 95.0,
        "atr": 2.0,
        "vol_ratio": 1.0,
        "adx": 25.0,
    }
    d.update(overrides)
    return d


class TestIntraday:
    def test_hold_on_neutral(self):
        signal, reasons = _get_signal_intraday(_base_indicators())
        assert signal == "HOLD"

    def test_buy_macd_cross_plus_rsi_gives_3(self):
        ind = _base_indicators(
            rsi=45.0,
            macd_hist=0.01,
            macd_hist_prev=-0.01,
        )
        signal, _ = _get_signal_intraday(ind)
        assert signal == "HOLD"

    def test_buy_at_threshold(self):
        ind = _base_indicators(
            rsi=45.0,
            macd_hist=0.01,
            macd_hist_prev=-0.01,
            price=93.0,
            vol_ratio=1.5,
        )
        signal, _ = _get_signal_intraday(ind)
        assert signal == "BUY"

    def test_sell_macd_bear_cross(self):
        ind = _base_indicators(
            rsi=72.0,
            macd_hist=-0.01,
            macd_hist_prev=0.01,
            price=108.0,
        )
        signal, _ = _get_signal_intraday(ind)
        assert signal == "SELL"

    def test_rsi_extremes(self):
        ind = _base_indicators(
            rsi=25.0,
            macd_hist=-0.01,
            macd_hist_prev=0.01,
            price=108.0,
            stoch_k=85.0,
        )
        signal, _ = _get_signal_intraday(ind)
        assert signal == "SELL"


class TestSwing:
    def test_adx_blocks_signal(self):
        ind = _base_indicators(adx=12.0)
        signal, reasons = _get_signal_swing(ind, bullish_market=True)
        assert signal == "HOLD"
        assert any("ADX muy bajo" in r for r in reasons)

    def test_adx_penalizes(self):
        ind = _base_indicators(
            adx=17.0,
            rsi=35.0,
            macd_hist=0.02,
            macd_hist_prev=-0.01,
            price=100.0,
            stoch_k=30.0,
            stoch_d=25.0,
            stoch_k_prev=24.0,
            stoch_d_prev=26.0,
            vol_ratio=1.5,
        )
        signal, reasons = _get_signal_swing(ind, bullish_market=True)
        assert any("ADX bajo" in r for r in reasons)

    def test_bullish_market_allows_buy(self):
        ind = _base_indicators(
            rsi=35.0,
            macd_hist=0.02,
            macd_hist_prev=-0.01,
            price=100.0,
            stoch_k=30.0,
            stoch_d=25.0,
            stoch_k_prev=24.0,
            stoch_d_prev=26.0,
            vol_ratio=1.5,
        )
        signal, _ = _get_signal_swing(ind, bullish_market=True)
        assert signal == "BUY"

    def test_bearish_market_blocks_buy(self):
        ind = _base_indicators(
            rsi=35.0,
            macd_hist=0.02,
            macd_hist_prev=-0.01,
            price=100.0,
            stoch_k=30.0,
            stoch_d=25.0,
            stoch_k_prev=24.0,
            stoch_d_prev=26.0,
            vol_ratio=1.5,
        )
        signal, reasons = _get_signal_swing(ind, bullish_market=False)
        assert signal == "HOLD"
        assert any("BUY bloqueado" in r for r in reasons)

    def test_gap_sell(self):
        ind = _base_indicators(
            gap_pct=3.0,
            rsi=73.0,
            macd_hist=-0.01,
            macd_hist_prev=0.01,
            price=100.0,
        )
        signal, _ = _get_signal_swing(ind, bullish_market=True)
        assert signal == "SELL"

    def test_panic_rsi_penalty(self):
        ind = _base_indicators(
            rsi=20.0,
            macd_hist=-0.01,
            macd_hist_prev=0.01,
            price=100.0,
        )
        signal, _ = _get_signal_swing(ind, bullish_market=True)
        assert signal == "SELL"


class TestCrypto:
    def test_crypto_hold_neutral(self):
        signal, _ = _get_signal_crypto(_base_indicators(), bullish_market=True)
        assert signal == "HOLD"

    def test_crypto_buy_with_macd_cross(self):
        ind = _base_indicators(
            rsi=35.0,
            macd_hist=0.01,
            macd_hist_prev=-0.01,
            price=93.0,
            stoch_k=20.0,
            vol_ratio=1.5,
        )
        signal, _ = _get_signal_crypto(ind, bullish_market=True)
        assert signal == "BUY"

    def test_crypto_bear_filter_blocks_buy(self):
        ind = _base_indicators(
            rsi=35.0,
            macd_hist=0.01,
            macd_hist_prev=-0.01,
            price=93.0,
            stoch_k=20.0,
            vol_ratio=1.5,
        )
        signal, reasons = _get_signal_crypto(ind, bullish_market=False)
        assert signal == "HOLD"
        assert any("BUY bloqueado" in r for r in reasons)

    def test_crypto_sell_signal(self):
        ind = _base_indicators(
            rsi=65.0,
            macd_hist=-0.01,
            macd_hist_prev=0.01,
            price=108.0,
            stoch_k=85.0,
        )
        signal, _ = _get_signal_crypto(ind, bullish_market=True)
        assert signal == "SELL"
