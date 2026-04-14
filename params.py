import os
import logging
from datetime import time as dtime
import pytz
from dotenv import load_dotenv

load_dotenv()

#log configuration to debug
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("StockPulse.log"),
    ],
)

log = logging.getLogger("stocks_bot")
#discord params
WEBHOOK  = os.getenv("DISCORD_WEBHOOK_URL", "")
INTERVAL = 30 * 60  #seconds between cycles

#timezone calculation
MARKET_TZ    = pytz.timezone("America/New_York")
MARKET_OPEN  = dtime(9, 30)
MARKET_CLOSE = dtime(16, 0)
MARKET_DAYS  = {0, 1, 2, 3, 4}  #mon-fri

#stocks
SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "AMD",  "JPM",  "SPY",
    "QQQ",  "NFLX"
]

#params
RSI_PERIOD  = 14
MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9
EMA_SHORT   = 20
EMA_LONG    = 50
BB_PERIOD   = 20
BB_STD      = 2
