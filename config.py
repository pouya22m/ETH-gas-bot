import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Bot Settings
ALERT_CHECK_INTERVAL = 300  # Check alerts every 5 minutes (in seconds)
ALERT_CHECK_FIRST_RUN = 10  # First check after 10 seconds

# Gas Limits (in gas units)
GAS_LIMITS = {
    'eth_transfer': 21000,
    'erc20_transfer': 65000,
    'token_swap': 356190,
    'nft_sale': 601953,
    'bridging': 114556,
    'borrowing': 302169
}

# Gas Status Thresholds (in Gwei)
GAS_STATUS_THRESHOLDS = {
    'low': 5,
    'normal': 10,
    'elevated': 30
}

# Alert Settings
MIN_ALERT_PRICE = 0.1
MAX_ALERT_PRICE = 1000
MAX_ALERTS_PER_USER = 10