# 📈 StockPulse

A Python algorithmic trading bot that scans a watchlist of US stocks, computes a suite of technical indicators, and fires **BUY / SELL** alerts to a Discord channel via webhook.

StockPulse supports two operating modes selectable via the `TRADING_MODE` environment variable — no code changes required:

| Mode | Candles | Scan frequency | BUY threshold | SELL threshold |
|---|---|---|---|---|
| `intraday` (default) | 30-minute | Every 30 min while NYSE is open | ≥ 4 | ≥ 3 |
| `swing` | Daily (1d) | Once per day at 09:35 ET | ≥ 5 | ≥ 4 |

***

## How it works

StockPulse runs a continuous loop. On each iteration it checks whether the NYSE is currently open (Monday–Friday, 09:30–16:00 ET). If the market is closed it sleeps in 5-minute blocks until the next opening bell; if it is open it executes one full scan cycle.

In **swing mode** the loop fires a single cycle at 09:35 ET each trading day instead of repeating every 30 minutes.

During a cycle, for every symbol in the watchlist:

1. **Fetch** — OHLCV candles are downloaded from Yahoo Finance via `yfinance` (7 days × 30 min in intraday; 6 months × 1d in swing).
2. **Compute** — all technical indicators are calculated with `pandas_ta`.
3. **Filter** *(swing only)* — if SPY is trading below its 50-day EMA, all BUY signals are suppressed for the entire cycle and a warning is sent to Discord.
4. **Score** — each indicator contributes points to a `buy_score` or `sell_score`.
5. **Decide** — if `buy_score ≥ threshold` → **BUY**; if `sell_score ≥ threshold` → **SELL**; otherwise **HOLD**.
6. **Alert** — BUY/SELL signals are sent as rich Discord embeds with all indicator values and the list of triggered reasons. Swing alerts include a T+1 hold reminder.

```text
StockPulse.py          ← main loop & cycle orchestration
params.py              ← all constants, env vars, watchlist
functions.py           ← market schedule, data fetching, indicators, signal logic
```

***

## Technical Indicators

All parameters are defined in `params.py` and passed to `functions.py`.

### 1 · RSI — Relative Strength Index
*Parameters: `RSI_PERIOD = 14`*

For each period $t$, let $\Delta_t = C_t - C_{t-1}$ where $C_t$ is the closing price.
Define the average gain and average loss over $N = 14$ periods using a smoothed (Wilder) moving average:

$$\bar{G}_t = \frac{(N-1)\,\bar{G}_{t-1} + \max(\Delta_t,\,0)}{N}, \qquad \bar{L}_t = \frac{(N-1)\,\bar{L}_{t-1} + \max(-\Delta_t,\,0)}{N}$$

The relative strength and the index are:

$$RS_t = \frac{\bar{G}_t}{\bar{L}_t}, \qquad RSI_t = 100 - \frac{100}{1 + RS_t}$$

Where:
- $C_t$: closing price at candle $t$
- $\Delta_t$: change in closing price between candles $t-1$ and $t$
- $\bar{G}_t$: smoothed average gain over $N$ periods
- $\bar{L}_t$: smoothed average loss over $N$ periods
- $RS_t$: relative strength at candle $t$
- $RSI_t$: final RSI value at candle $t$

**Bot thresholds:**

| Condition | Score |
|---|---|
| $35 \leq RSI \leq 58$ | +1 BUY |
| $RSI > 68$ | +1 SELL |
| $RSI < 32$ | +1 SELL |

***

### 2 · MACD — Moving Average Convergence Divergence
*Parameters: `MACD_FAST = 12`, `MACD_SLOW = 26`, `MACD_SIGNAL = 9`*

The MACD line is the difference between two EMAs of the closing price:

$$MACD_t = EMA_{12}(C)_t - EMA_{26}(C)_t$$

The signal line is a 9-period EMA of the MACD line:

$$Signal_t = EMA_9(MACD)_t$$

The histogram is:

$$H_t = MACD_t - Signal_t$$

Where:
- $EMA_{12}(C)_t$: 12-period exponential moving average of close
- $EMA_{26}(C)_t$: 26-period exponential moving average of close
- $MACD_t$: momentum spread between short and long EMAs
- $Signal_t$: smoothed MACD line
- $H_t$: MACD histogram at candle $t$
- $H_{t-1}$: MACD histogram at the previous candle

**Bot crossover logic:**

| Condition | Score |
|---|---|
| $H_t > 0$ and $H_{t-1} \leq 0$ (bullish cross) | **+2 BUY** |
| $H_t < 0$ and $H_{t-1} \geq 0$ (bearish cross) | **+2 SELL** |

***

### 3 · EMA — Exponential Moving Average
*Parameters: `EMA_SHORT = 20`, `EMA_LONG = 50`*

For an EMA of length $N$, the smoothing factor is:

$$k = \frac{2}{N + 1}$$

The recursive EMA formula is:

$$EMA_t = C_t \cdot k + EMA_{t-1} \cdot (1 - k)$$

Where:
- $C_t$: current closing price at candle $t$
- $EMA_{t-1}$: EMA value from the previous candle
- $k$: smoothing multiplier (for $N=20$: $k \approx 0.095$; for $N=50$: $k \approx 0.038$)
- $EMA_t$: updated EMA at candle $t$

**Bot thresholds:**

| Condition | Score |
|---|---|
| $C_t > EMA_{20,t} > EMA_{50,t}$ | +1 BUY |
| $C_t < EMA_{20,t}$ | +1 SELL |

***

### 4 · Bollinger Bands
*Parameters: `BB_PERIOD = 20`, `BB_STD = 2`*

The middle band is the 20-period simple moving average:

$$\mu_t = \frac{1}{N}\sum_{i=0}^{N-1} C_{t-i}$$

The rolling standard deviation over the same window:

$$\sigma_t = \sqrt{\frac{1}{N}\sum_{i=0}^{N-1}\left(C_{t-i} - \mu_t\right)^2}$$

The three bands are:

$$BB_{upper,t} = \mu_t + 2\sigma_t, \qquad BB_{mid,t} = \mu_t, \qquad BB_{lower,t} = \mu_t - 2\sigma_t$$

Where:
- $\mu_t$: 20-period mean of closing prices
- $\sigma_t$: 20-period standard deviation of closing prices
- $BB_{upper,t}$: upper band
- $BB_{mid,t}$: middle band (moving average)
- $BB_{lower,t}$: lower band

**Bot thresholds:**

| Condition | Score |
|---|---|
| $C_t \leq BB_{mid,t}$ | +1 BUY |
| $C_t \geq 0.98 \cdot BB_{upper,t}$ | +1 SELL |

***

### 5 · ATR — Average True Range
*Parameter: 14 periods*

The True Range at time $t$ captures the largest of three possible price gaps:

$$TR_t = \max\!\Big(H_t - L_t,\;\; \left|H_t - C_{t-1}\right|,\;\; \left|L_t - C_{t-1}\right|\Big)$$

The ATR is the exponentially smoothed true range:

$$ATR_t = EMA_{14}(TR)_t$$

Where:
- $H_t$: current candle high
- $L_t$: current candle low
- $C_{t-1}$: previous candle close
- $TR_t$: true range at candle $t$
- $ATR_t$: average true range at candle $t$

ATR is computed and included in every Discord alert as context. It is **not used in the scoring rules** — it is available for future extensions such as position sizing or dynamic stop-loss placement.

***

### 6 · Volume Ratio
*Parameter: rolling 20-candle volume mean*

$$VolRatio_t = \frac{V_t}{\overline{V}_{t,20}}$$

Where:
- $V_t$: volume of the current candle
- $\overline{V}_{t,20}$: simple moving average of volume over the last 20 candles
- $VolRatio_t$: relative volume strength of the current candle

A ratio above 1.2 means the current candle carries at least 20% more volume than the recent average, increasing confidence that a price move is backed by real market participation.

**Bot threshold:**

| Condition | Score |
|---|---|
| $VolRatio_t > 1.2$ | +1 BUY |

***

### 7 · Stochastic RSI
*Parameter: 14 periods, K smoothing = 3*

This indicator applies the stochastic normalization formula to RSI values, making it more sensitive to short-term momentum shifts than raw RSI.

The raw StochRSI normalizes the current RSI within its own recent range:

$$StochRSI_{raw,t} = \frac{RSI_t - \min_{[t-N+1,\, t]}(RSI)}{\max_{[t-N+1,\, t]}(RSI) - \min_{[t-N+1,\, t]}(RSI)}$$

The bot uses the smoothed %K line:

$$K_t = EMA_3\!\left(StochRSI_{raw}\right)_t$$

Where:
- $RSI_t$: RSI value at candle $t$
- $\min_{[t-N+1,\,t]}(RSI)$: minimum RSI over the last 14 candles
- $\max_{[t-N+1,\,t]}(RSI)$: maximum RSI over the last 14 candles
- $StochRSI_{raw,t}$: position of current RSI within its 14-period range, in $[1]$
- $K_t$: 3-period smoothed StochRSI, scaled to $$

**Bot thresholds:**

| Condition | Score |
|---|---|
| $K_t < 25$ | +1 BUY |
| $K_t > 80$ | +1 SELL |

***

## Signal Decision Logic

All seven indicators are evaluated simultaneously for every candle. Each triggered condition adds points to `buy_score` or `sell_score`. The decision function is:

$$Signal = \begin{cases} \textbf{BUY} & \text{if } buy\_score \geq threshold_{BUY} \\ \textbf{SELL} & \text{if } sell\_score \geq threshold_{SELL} \\ \textbf{HOLD} & \text{otherwise} \end{cases}$$

The SELL threshold is intentionally lower than BUY to exit positions more reactively than entering them. In swing mode both thresholds are raised by 1 to reduce noise on the daily timeframe, and BUY signals are additionally suppressed when SPY trades below its 50-day EMA.

**Full scoring table:**

| Indicator | Condition | Score |
|---|---|---|
| RSI | $35 \leq RSI \leq 58$ | +1 BUY |
| RSI | $RSI > 68$ | +1 SELL |
| RSI | $RSI < 32$ | +1 SELL |
| MACD | $H_t > 0$ and $H_{t-1} \leq 0$ | **+2 BUY** |
| MACD | $H_t < 0$ and $H_{t-1} \geq 0$ | **+2 SELL** |
| EMA | $C_t > EMA_{20} > EMA_{50}$ | +1 BUY |
| EMA | $C_t < EMA_{20}$ | +1 SELL |
| Bollinger Bands | $C_t \leq BB_{mid}$ | +1 BUY |
| Bollinger Bands | $C_t \geq 0.98 \cdot BB_{upper}$ | +1 SELL |
| Volume Ratio | $VolRatio > 1.2$ | +1 BUY |
| Stochastic RSI | $K < 25$ | +1 BUY |
| Stochastic RSI | $K > 80$ | +1 SELL |

Maximum possible BUY score: **9** · Maximum possible SELL score: **8**

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

1. Open your Discord server → right-click the target channel → **Edit Channel**
2. Go to **Integrations → Webhooks → New Webhook**
3. Copy the webhook URL

### 3. Configure environment variables

Create a `.env` file:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
TRADING_MODE=swing
```

`TRADING_MODE` accepts `intraday` (default) or `swing`.

### 4. Run locally

```bash
python StockPulse.py
```

The bot logs every scan cycle to the console and to `StockPulse.log`. Discord alerts are only sent when a BUY or SELL signal is triggered.

### 5. Deploy
This bot is designed to be deployed and run 24/7 on a server, may this be whichever you prefer.

## Watchlist

Defined in `params.py` under `SYMBOLS`. Default (60 symbols):

```
AAPL  MSFT  GOOGL  AMZN  META  NVDA  PLTR  NOW  SNOW  ADBE
AVGO  QCOM  MU  AMAT  TSLA  JPM  V  BX  PYPL  LLY
UNH  ISRG  TMO  XOM  NEE  COST  MCD  NKE  RTX  CAT
SPY  MSTR  HOOD  COIN  RBLX  DKNG  LMT  NOC  GD  MRNA
RXRX  CRSP  AFRM  NU  CRWD  ZS  NET  DDOG  ABNB  UBER
SPOT  GE  PWR  FCX  NEM  SHOP  MELI  GLD
```

Edit the list freely — any ticker supported by Yahoo Finance works.


> **Disclaimer:** StockPulse is an educational project. Signals are based on technical analysis and do not constitute financial advice. Always do your own research before making any investment decision.