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
    # Tech megacap
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    # AI & software
    "NVDA", "PLTR", "NOW", "SNOW", "ADBE",
    # Semiconductores
    "AVGO", "QCOM", "MU", "AMAT",
    # EV
    "TSLA",
    # Finanzas
    "JPM", "V", "BX", "PYPL",
    # Salud
    "LLY", "UNH", "ISRG", "TMO",
    # Energía
    "XOM", "NEE",
    # Consumer
    "COST", "MCD", "NKE",
    # Industrial / Defensa
    "RTX", "CAT",
    # Macro
    "SPY",
    # High-momentum
    "MSTR", "HOOD", "COIN", "RBLX", "DKNG",
    # Defensa extra
    "LMT", "NOC", "GD",
    # Biotech agresiva
    "MRNA", "RXRX", "CRSP",
    # Fintech
    "AFRM", "NU",
    # Cloud & ciberseguridad
    "CRWD", "ZS", "NET", "DDOG",
    # Consumer lifestyle
    "ABNB", "UBER", "SPOT",
    # Industrial
    "GE", "PWR",
    # Commodities proxy
    "FCX", "NEM",
    # Retail moderno
    "SHOP", "MELI",
    # Macro refugio
    "GLD",
]
#params
RSI_PERIOD  = 14
MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9
EMA_SHORT   = 20
EMA_LONG    = 50
BB_PERIOD   = 20
BB_STD      = 2.0
