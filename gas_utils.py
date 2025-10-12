import requests
from datetime import datetime
from config import ETHERSCAN_API_KEY, GAS_LIMITS, GAS_STATUS_THRESHOLDS


def fetch_gas_data():
    """Fetch gas data from Etherscan API"""
    url = "https://api.etherscan.io/v2/api"
    params = {
        'chainid': 1,
        'module': 'gastracker',
        'action': 'gasoracle',
        'apikey': ETHERSCAN_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == '1':
            return data['result']
        return None
    except Exception as e:
        print(f"Error fetching gas data: {e}")
        return None


def get_eth_price():
    """Fetch current ETH price in USD"""
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
            timeout=10
        )
        data = response.json()
        return data['ethereum']['usd']
    except Exception as e:
        print(f"Error fetching ETH price: {e}")
        return 2500  # Fallback


def calculate_tx_cost(gas_price_gwei, gas_limit, eth_price):
    """Calculate transaction cost in USD"""
    try:
        gas_price = float(gas_price_gwei)
        gas_price_eth = gas_price * 1e-9
        cost_eth = gas_price_eth * gas_limit
        cost_usd = cost_eth * eth_price
        return cost_usd
    except Exception as e:
        print(f"Error calculating tx cost: {e}")
        return 0


def get_gas_status(gas_price):
    """Determine gas status based on price"""
    try:
        gas = float(gas_price)
        if gas < GAS_STATUS_THRESHOLDS['low']:
            return "🟢 Gas is LOW", "Good time to transact!"
        elif gas < GAS_STATUS_THRESHOLDS['normal']:
            return "🟡 Gas is NORMAL", "Standard network activity"
        elif gas < GAS_STATUS_THRESHOLDS['elevated']:
            return "🟠 Gas is ELEVATED", "Consider waiting if not urgent"
        else:
            return "🔴 Gas is HIGH", "Wait if transaction is not urgent!"
    except:
        return "🟡 Gas is NORMAL", "Standard network activity"


def get_trend_indicator(current_gas, base_fee):
    """Improved trend indicator"""
    try:
        current = float(current_gas)
        base = float(base_fee)
        diff_percent = ((current - base) / base) * 100
        
        if diff_percent > 10:
            return "↗️ Rising Fast"
        elif diff_percent > 3:
            return "↗️ Rising"
        elif diff_percent < -10:
            return "↘️ Falling Fast"
        elif diff_percent < -3:
            return "↘️ Falling"
        else:
            return "➡️ Stable"
    except:
        return "➡️ Stable"


def format_gas_message(gas_data, eth_price):
    """Format gas data into a beautiful message"""
    if not gas_data:
        return "❌ Unable to fetch gas data. Please try again later."
    
    safe_gas = gas_data.get('SafeGasPrice', 'N/A')
    propose_gas = gas_data.get('ProposeGasPrice', 'N/A')
    fast_gas = gas_data.get('FastGasPrice', 'N/A')
    base_fee = gas_data.get('suggestBaseFee', propose_gas)
    
    status_emoji, status_text = get_gas_status(propose_gas)
    trend = get_trend_indicator(propose_gas, base_fee)
    
    # Calculate costs
    try:
        simple_transfer = calculate_tx_cost(propose_gas, GAS_LIMITS['eth_transfer'], eth_price)
        erc20_transfer = calculate_tx_cost(propose_gas, GAS_LIMITS['erc20_transfer'], eth_price)
        token_swap = calculate_tx_cost(propose_gas, GAS_LIMITS['token_swap'], eth_price)
        nft_sale = calculate_tx_cost(propose_gas, GAS_LIMITS['nft_sale'], eth_price)
        bridging = calculate_tx_cost(propose_gas, GAS_LIMITS['bridging'], eth_price)
        borrowing = calculate_tx_cost(propose_gas, GAS_LIMITS['borrowing'], eth_price)
    except:
        simple_transfer = erc20_transfer = token_swap = nft_sale = bridging = borrowing = 0
    
    # Format gas prices
    try:
        safe_gas_fmt = f"{float(safe_gas):.2f}"
        propose_gas_fmt = f"{float(propose_gas):.2f}"
        fast_gas_fmt = f"{float(fast_gas):.2f}"
        base_fee_fmt = f"{float(base_fee):.2f}"
    except:
        safe_gas_fmt = safe_gas
        propose_gas_fmt = propose_gas
        fast_gas_fmt = fast_gas
        base_fee_fmt = base_fee
    
    message = f"""⛽ <b>Ethereum Gas Tracker</b>

{status_emoji} <b>{status_text}</b>

<b>Current Gas Prices:</b>
🐌 Low: {safe_gas_fmt} Gwei
⚡ Standard: {propose_gas_fmt} Gwei
🚀 Fast: {fast_gas_fmt} Gwei

<b>💰 Transaction Costs (Standard):</b>
- ETH Transfer: ${simple_transfer:.2f}
- ERC20 Transfer: ${erc20_transfer:.2f}
- Token Swap: ${token_swap:.2f}
- NFT Sale: ${nft_sale:.2f}
- Bridge to L2: ${bridging:.2f}
- DeFi Borrow: ${borrowing:.2f}

<b>📊 Network Info:</b>
- Base Fee: {base_fee_fmt} Gwei
- Trend: {trend}
- ETH Price: ${eth_price:,.2f}

🕐 <i>Updated: {datetime.now().strftime('%H:%M:%S UTC')}</i>"""
    
    return message