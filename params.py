import os
import logging
from datetime import time as dtime
import pytz
from dotenv import load_dotenv

load_dotenv()

#logging configuration for debugging and monitoring
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("StockPulse.log"),
    ],
)
log = logging.getLogger("stocks_bot")

TRADING_MODE = os.getenv("TRADING_MODE", "intraday").lower()

# discord
WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")

#NYSE timezone
MARKET_TZ    = pytz.timezone("America/New_York")
MARKET_OPEN  = dtime(9, 30)
MARKET_CLOSE = dtime(16, 0)
MARKET_DAYS  = {0, 1, 2, 3, 4}  # mon-fri

#parameters by mode
if TRADING_MODE == "intraday":
    DATA_INTERVAL = "30m"
    DATA_PERIOD = "7d"
    MIN_CANDLES = 60
    SCAN_INTERVAL = 30 * 60
    SCAN_HOUR_ET = None
    SCAN_MINUTE_ET = None
    BUY_THRESHOLD = 4
    SELL_THRESHOLD = 3
elif TRADING_MODE == "crypto":
    DATA_INTERVAL = "30m"
    DATA_PERIOD = "7d"
    MIN_CANDLES = 40
    SCAN_INTERVAL = 30 * 60
    SCAN_HOUR_ET = None
    SCAN_MINUTE_ET = None
    BUY_THRESHOLD = 5
    SELL_THRESHOLD = 4
else:  # swing
    DATA_INTERVAL = "1d"
    DATA_PERIOD = "6mo"
    MIN_CANDLES = 60
    SCAN_INTERVAL = None
    SCAN_HOUR_ET = 9
    SCAN_MINUTE_ET = 35
    BUY_THRESHOLD = 5
    SELL_THRESHOLD = 4

#stocks
SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    "NVDA", "PLTR", "NOW", "SNOW", "ADBE",
    "AVGO", "QCOM", "MU", "AMAT",
    "TSLA",
    "JPM", "V", "BX", "PYPL",
    "LLY", "UNH", "ISRG", "TMO",
    "XOM", "NEE",
    "COST", "MCD", "NKE",
    "RTX", "CAT",
    "SPY",
    "MSTR", "HOOD", "COIN", "RBLX", "DKNG",
    "LMT", "NOC", "GD",
    "MRNA", "RXRX", "CRSP",
    "AFRM", "NU",
    "CRWD", "ZS", "NET", "DDOG",
    "ABNB", "UBER", "SPOT",
    "GE", "PWR",
    "FCX", "NEM",
    "SHOP", "MELI",
    "GLD",
]

CRYPTO_SYMBOLS = ["BTC-USD", "ETH-USD", "LTC-USD", "BCH-USD", "SOL-USD"]

#index parameters
RSI_PERIOD  = 14
MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9
EMA_SHORT   = 20
EMA_LONG    = 50
BB_PERIOD   = 20
BB_STD      = 2.0
