# StockPulse

A Python algorithmic trading bot that scans watchlists of US stocks and cryptocurrencies, computes a suite of technical indicators, and fires **BUY / SELL** alerts to a Discord channel via webhook.

## Quick start

```bash
git clone https://github.com/moizefala1/StockPulse
cd StockPulse
pip install -r requirements.txt
# Create .env with your Discord webhook URL and desired mode (see Setup below)
python StockPulse.py
```

StockPulse supports three modes via the `TRADING_MODE` environment variable:

| Mode | Asset class | Candles | Scan frequency | BUY thr. | SELL thr. | Macro filter |
|---|---|---|---|---|---|---|
| `intraday` (default) | US stocks | 30m | every 30 min while NYSE is open | 4 | 3 | none |
| `swing` | US stocks | 1d | once/day at 09:35 ET | 4 | 3 | SPY vs EMA50 (daily) |
| `crypto` | crypto (top 5) | 30m | every 30 min (24/7) | 5 | 4 | BTC vs EMA50 (4h) |

**Switch modes** by changing `TRADING_MODE` in your `.env` and restarting — no code changes required:

```env
TRADING_MODE=intraday   # scan stocks every 30 min while NYSE is open
TRADING_MODE=swing      # scan stocks once a day at 09:35 ET
TRADING_MODE=crypto     # scan crypto 24/7 every 30 min
```

***

## How it works

StockPulse runs a continuous loop. In **intraday** and **crypto** modes it scans every 30 minutes (drift-corrected — cycle time is subtracted from the sleep interval). In **swing** mode it fires a single scan at 09:35 ET each trading day and waits for the next session.

The intraday and swing runners use the real NYSE calendar (`pandas_market_calendars`) — holidays and early closes are handled correctly. The crypto runner runs 24/7.

During a scan cycle, all symbols in the watchlist are processed **concurrently** (8 workers):

1. **Fetch** — OHLCV candles are downloaded from Yahoo Finance via `yfinance`.
2. **Compute** — technical indicators are calculated with `pandas_ta`.
3. **Filter** *(swing & crypto only)* — if the macro benchmark (SPY or BTC) is trading below its 50-period EMA, BUY signals are suppressed and a warning is sent to Discord.
4. **Score** — each indicator contributes points to a `buy_score` or `sell_score`.
5. **Decide** — if `buy_score >= threshold` → **BUY**; if `sell_score >= threshold` → **SELL**; otherwise **HOLD**.
6. **Alert** — BUY/SELL signals are sent as rich Discord embeds with all indicator values and the list of triggered reasons.

### Architecture

```text
StockPulse.py          top-level entrypoint — mode dispatch, continuous loops
params.py              all constants, env vars, watchlists, mode-specific config
functions.py           market schedule, data fetching, indicators, signal scoring
```

Three source files. `params.py` exposes an `init()` function that loads `.env`, sets up logging, and configures mode-specific constants. **`init()` must be called before importing `functions`** — `StockPulse.py` does this at the top.

The three modes use **three separate signal functions** in `functions.py` — `_get_signal_intraday`, `_get_signal_swing`, `_get_signal_crypto` — each with different scoring rules, RSI thresholds, and ADX/gap logic where applicable.

***

## Technical Indicators

All parameters are defined in `params.py` and passed to `functions.py`.

### 1 - RSI — Relative Strength Index
*Parameters: `RSI_PERIOD = 14`*

$$\bar{G}_t = \frac{(N-1)\,\bar{G}_{t-1} + \max(\Delta_t,\,0)}{N}, \qquad \bar{L}_t = \frac{(N-1)\,\bar{L}_{t-1} + \max(-\Delta_t,\,0)}{N}$$

$$RS_t = \frac{\bar{G}_t}{\bar{L}_t}, \qquad RSI_t = 100 - \frac{100}{1 + RS_t}$$

Thresholds vary per mode. In **intraday**: +1 BUY if RSI `[30, 70]`, +1 SELL if `>70` or `<30`. In **swing**: two-tier buy zone (`<=38` and `38-45`), two-tier sell zone (`>72` and `65-72`), and extreme panic penalty (`<25`, +2 SELL). In **crypto**: +1 BUY if `<40`, +1 SELL if `>60`.

### 2 - MACD — Moving Average Convergence Divergence
*Parameters: `MACD_FAST = 12`, `MACD_SLOW = 26`, `MACD_SIGNAL = 9`*

$$MACD_t = EMA_{12}(C)_t - EMA_{26}(C)_t, \qquad Signal_t = EMA_9(MACD)_t, \qquad H_t = MACD_t - Signal_t$$

Bullish cross ($H_t > 0$ and $H_{t-1} \leq 0$): **+2 BUY**. Bearish cross ($H_t < 0$ and $H_{t-1} \geq 0$): **+2 SELL**. In **swing** mode, sustained histogram direction (positive or negative without a fresh cross) also contributes +1.

### 3 - EMA — Exponential Moving Average
*Parameters: `EMA_SHORT = 20`, `EMA_LONG = 50`*

$$EMA_t = C_t \cdot k + EMA_{t-1} \cdot (1 - k), \qquad k = \frac{2}{N + 1}$$

+1 BUY when price aligns above both EMAs ($C_t > EMA_{20} > EMA_{50}$). +1 SELL when price drops below EMA20. Swing mode adds an intermediate credit for price above EMA20 without the EMA50 alignment.

### 4 - Bollinger Bands
*Parameters: `BB_PERIOD = 20`, `BB_STD = 2`*

$$BB_{upper} = \mu_t + 2\sigma_t, \qquad BB_{mid} = \mu_t, \qquad BB_{lower} = \mu_t - 2\sigma_t$$

+1 BUY when price is at or below the middle band. +1 SELL when price is within 2% of the upper band ($C_t \geq 0.98 \cdot BB_{upper}$).

### 5 - ATR — Average True Range
*Parameter: 14 periods*

$$TR_t = \max(H_t - L_t,\;\; |H_t - C_{t-1}|,\;\; |L_t - C_{t-1}|), \qquad ATR_t = EMA_{14}(TR)_t$$

ATR is computed and included in every Discord alert as context. It is not used in scoring — available for future position sizing or dynamic stop-loss.

### 6 - Volume Ratio
*Parameter: rolling 20-candle volume mean*

$$VolRatio_t = \frac{V_t}{\overline{V}_{t,20}}$$

+1 BUY when volume is at least 20% above average ($VolRatio_t > 1.2$), confirming the move has market participation.

### 7 - Stochastic RSI
*Parameter: 14 periods, K smoothing = 3*

$$StochRSI_{raw,t} = \frac{RSI_t - \min_{[t-N+1,\, t]}(RSI)}{\max_{[t-N+1,\, t]}(RSI) - \min_{[t-N+1,\, t]}(RSI)}, \qquad K_t = EMA_3(StochRSI_{raw})_t$$

+1 BUY when $K_t < 25$ (oversold). +1 SELL when $K_t > 80$ (overbought). In **swing** mode, K/D crossovers with volume confirmation can contribute +2.

***

## Signal Decision Logic

All indicators are evaluated simultaneously. Each triggered condition adds points to `buy_score` or `sell_score`:

$$Signal = \begin{cases} \textbf{BUY} & \text{if } buy\_score \geq threshold_{BUY} \\ \textbf{SELL} & \text{if } sell\_score \geq threshold_{SELL} \\ \textbf{HOLD} & \text{otherwise} \end{cases}$$

The SELL threshold is intentionally lower than BUY to exit positions more reactively than entering them.

Additional logic per mode:
- **Swing**: ADX below 15 blocks all signals entirely (sideways market). ADX between 15-20 penalizes both scores by 1. Overnight gap behavior is scored — gap-downs above EMA20 (+1 BUY) and gap-ups above 2.5% (+1 SELL).
- **Crypto**: excludes ADX and gap scoring. Uses higher thresholds (5/4) to reduce noise on volatile assets.

***

## Setup

### Prerequisites

- Python 3.12+
- A Discord server where you have permission to create webhooks

### 1. Clone and install dependencies

```bash
git clone https://github.com/moizefala1/StockPulse
cd StockPulse
pip install -r requirements.txt
```

### 2. Create your Discord webhook

1. Open your Discord server -> right-click the target channel -> **Edit Channel**
2. Go to **Integrations -> Webhooks -> New Webhook**
3. Copy the webhook URL

### 3. Configure environment variables

Create a `.env` file:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
TRADING_MODE=swing
```

`TRADING_MODE` accepts `intraday` (default), `swing`, or `crypto`. The webhook is optional — if omitted, alerts are logged to console only.

### 4. Run locally

```bash
python StockPulse.py
```

The bot logs every scan cycle to the console and to `StockPulse.log`. Discord alerts are only sent when a BUY or SELL signal is triggered.

***

## Watchlists

Defined in `params.py`.

**Stocks** (`SYMBOLS`, 58 tickers):

```
AAPL  MSFT  GOOGL  AMZN  META  NVDA  PLTR  NOW  SNOW  ADBE
AVGO  QCOM  MU  AMAT  TSLA  JPM  V  BX  PYPL  LLY
UNH  ISRG  TMO  XOM  NEE  COST  MCD  NKE  RTX  CAT
SPY  MSTR  HOOD  COIN  RBLX  DKNG  LMT  NOC  GD  MRNA
RXRX  CRSP  AFRM  NU  CRWD  ZS  NET  DDOG  ABNB  UBER
SPOT  GE  PWR  FCX  NEM  SHOP  MELI  GLD
```

**Crypto** (`CRYPTO_SYMBOLS`, 5 coins): `BTC-USD`, `ETH-USD`, `LTC-USD`, `BCH-USD`, `SOL-USD`

Edit the lists freely — any ticker supported by Yahoo Finance works.

***

## Development

```bash
ruff check .              # linter
ruff format --check .     # formatter (dry-run)
ruff format .             # auto-format
pytest tests/ -q          # run test suite (15 tests)
```

The project uses a hybrid import model: `params.init()` loads `.env`, configures logging, and sets mode-specific constants. It must be called before `functions` is imported — enforced by `# noqa: E402` in `StockPulse.py` and tests.

The test suite covers all three signal functions with mocked indicator dicts. Tests do not hit the network.

Deploy anywhere — the `Dockerfile` and `railway.toml` are included for 24/7 operation on Railway or any Docker host.

***

> **Disclaimer:** StockPulse is an educational project. Signals are based on technical analysis and do not constitute financial advice. Always do your own research before making any investment decision.
