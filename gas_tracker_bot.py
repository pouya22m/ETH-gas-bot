import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Load environment variables
load_dotenv()

ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')


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
    except:
        return 2500  # Fallback to default

def calculate_tx_cost(gas_price_gwei, gas_limit, eth_price):
    """Calculate transaction cost in USD"""
    gas_price_eth = float(gas_price_gwei) * 1e-9
    cost_eth = gas_price_eth * gas_limit
    cost_usd = cost_eth * eth_price
    return cost_usd

def get_gas_status(gas_price):
    """Determine gas status based on price"""
    gas = float(gas_price)
    if gas < 15:
        return "🟢 Gas is LOW", "Good time to transact!"
    elif gas < 30:
        return "🟡 Gas is NORMAL", "Standard network activity"
    elif gas < 50:
        return "🟠 Gas is ELEVATED", "Consider waiting if not urgent"
    else:
        return "🔴 Gas is HIGH", "Wait if transaction is not urgent!"

def get_trend_indicator(gas_price, base_fee):
    """Simple trend indicator"""
    try:
        gas = float(gas_price)
        base = float(base_fee)
        diff = gas - base
        
        if diff > 2:
            return "↗️ Rising"
        elif diff < -2:
            return "↘️ Falling"
        else:
            return "➡️ Stable"
    except:
        return "➡️ Stable"

def format_gas_message(gas_data, eth_price):
    """Format gas data into a beautiful message"""
    if not gas_data:
        return "❌ Unable to fetch gas data. Please try again later."
    
    # Extract gas prices
    safe_gas = gas_data.get('SafeGasPrice', 'N/A')
    propose_gas = gas_data.get('ProposeGasPrice', 'N/A')
    fast_gas = gas_data.get('FastGasPrice', 'N/A')
    base_fee = gas_data.get('suggestBaseFee', propose_gas)
    
    # Get status
    status_emoji, status_text = get_gas_status(propose_gas)
    trend = get_trend_indicator(propose_gas, base_fee)
    
    # Calculate costs for standard gas price with CORRECT gas limits
    try:
        # Using realistic gas limits based on Etherscan data
        simple_transfer = calculate_tx_cost(propose_gas, 21000, eth_price)      # ETH transfer
        token_swap = calculate_tx_cost(propose_gas, 184000, eth_price)          # Uniswap swap
        nft_sale = calculate_tx_cost(propose_gas, 170000, eth_price)            # OpenSea/NFT sale
        bridging = calculate_tx_cost(propose_gas, 120000, eth_price)            # L2 bridge
        borrowing = calculate_tx_cost(propose_gas, 250000, eth_price)           # Aave/Compound
        
        # Calculate for Low gas
        simple_transfer_low = calculate_tx_cost(safe_gas, 21000, eth_price)
        token_swap_low = calculate_tx_cost(safe_gas, 184000, eth_price)
        nft_sale_low = calculate_tx_cost(safe_gas, 170000, eth_price)
        bridging_low = calculate_tx_cost(safe_gas, 120000, eth_price)
        borrowing_low = calculate_tx_cost(safe_gas, 250000, eth_price)
        
        # Calculate for Fast gas
        simple_transfer_fast = calculate_tx_cost(fast_gas, 21000, eth_price)
        token_swap_fast = calculate_tx_cost(fast_gas, 184000, eth_price)
        nft_sale_fast = calculate_tx_cost(fast_gas, 170000, eth_price)
        bridging_fast = calculate_tx_cost(fast_gas, 120000, eth_price)
        borrowing_fast = calculate_tx_cost(fast_gas, 250000, eth_price)
    except:
        simple_transfer = token_swap = nft_sale = bridging = borrowing = 0
        simple_transfer_low = token_swap_low = nft_sale_low = bridging_low = borrowing_low = 0
        simple_transfer_fast = token_swap_fast = nft_sale_fast = bridging_fast = borrowing_fast = 0
    
    # Build message with improved formatting
    message = f"""⛽ <b>Ethereum Gas Tracker</b>

{status_emoji} <b>{status_text}</b>

<b>Current Gas Prices:</b>
🐌 Low: {safe_gas} Gwei
⚡ Standard: {propose_gas} Gwei
🚀 Fast: {fast_gas} Gwei

<b>💰 Transaction Costs:</b>

<b>ETH Transfer (21k gas)</b>
Low: ${simple_transfer_low:.2f} | Avg: ${simple_transfer:.2f} | Fast: ${simple_transfer_fast:.2f}

<b>Token Swap (184k gas)</b>
Low: ${token_swap_low:.2f} | Avg: ${token_swap:.2f} | Fast: ${token_swap_fast:.2f}

<b>NFT Sale (170k gas)</b>
Low: ${nft_sale_low:.2f} | Avg: ${nft_sale:.2f} | Fast: ${nft_sale_fast:.2f}

<b>Bridge to L2 (120k gas)</b>
Low: ${bridging_low:.2f} | Avg: ${bridging:.2f} | Fast: ${bridging_fast:.2f}

<b>DeFi Borrow (250k gas)</b>
Low: ${borrowing_low:.2f} | Avg: ${borrowing:.2f} | Fast: ${borrowing_fast:.2f}

<b>📊 Network Info:</b>
- Base Fee: {base_fee} Gwei
- Trend: {trend}
- ETH Price: ${eth_price:,.2f}

🕐 <i>Updated: {datetime.now().strftime('%H:%M:%S UTC')}</i>"""
    
    return message

def create_keyboard():
    """Create inline keyboard with action buttons"""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
            InlineKeyboardButton("📊 History", callback_data="history")
        ],
        [
            InlineKeyboardButton("⏰ Set Alert", callback_data="alert"),
            InlineKeyboardButton("ℹ️ Help", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_message = """👋 <b>Welcome to Ethereum Gas Tracker Bot!</b>

I help you monitor Ethereum gas prices in real-time.

<b>Commands:</b>
/gas - Get current gas prices
/help - Show help information

Click the button below to check current gas prices! ⬇️"""
    
    keyboard = [[InlineKeyboardButton("⛽ Check Gas Prices", callback_data="refresh")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def gas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /gas command"""
    # Send "loading" message
    message = await update.message.reply_text("⏳ Fetching current gas prices...")
    
    # Fetch data
    gas_data = fetch_gas_data()
    eth_price = get_eth_price()
    
    # Format and send message
    gas_message = format_gas_message(gas_data, eth_price)
    keyboard = create_keyboard()
    
    await message.edit_text(
        gas_message,
        parse_mode='HTML',
        reply_markup=keyboard
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """<b>🤖 Gas Tracker Bot Help</b>

<b>Commands:</b>
/start - Start the bot
/gas - Get current gas prices
/help - Show this help message

<b>Understanding Gas Prices:</b>
- <b>Low (Safe)</b>: Cheapest option, slower confirmation
- <b>Standard</b>: Balanced speed and cost
- <b>Fast</b>: Priority processing, higher cost

<b>Gas Status Colors:</b>
🟢 LOW - Great time to transact!
🟡 NORMAL - Standard network activity
🟠 ELEVATED - Consider waiting
🔴 HIGH - Wait if not urgent

<b>Tips:</b>
- Gas is typically lower on weekends
- Early morning UTC often has lower gas
- Use "Low" for non-urgent transactions

Need more help? Contact @YourSupportUsername"""
    
    await update.message.reply_text(help_text, parse_mode='HTML')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "refresh":
        # Update message with loading state
        await query.edit_message_text("⏳ Fetching latest gas prices...")
        
        # Fetch fresh data
        gas_data = fetch_gas_data()
        eth_price = get_eth_price()
        
        # Update message
        gas_message = format_gas_message(gas_data, eth_price)
        keyboard = create_keyboard()
        
        await query.edit_message_text(
            gas_message,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    
    elif query.data == "history":
        await query.edit_message_text(
            "📊 <b>Gas History Feature</b>\n\n"
            "This feature is coming soon! It will show:\n"
            "• 24-hour gas price chart\n"
            "• Average prices\n"
            "• Best times to transact\n\n"
            "Stay tuned! 🚀",
            parse_mode='HTML',
            reply_markup=create_keyboard()
        )
    
    elif query.data == "alert":
        await query.edit_message_text(
            "⏰ <b>Price Alert Feature</b>\n\n"
            "This feature is coming soon! You'll be able to:\n"
            "• Set custom gas price alerts\n"
            "• Get notified when gas drops\n"
            "• Subscribe to daily reports\n\n"
            "Stay tuned! 🔔",
            parse_mode='HTML',
            reply_markup=create_keyboard()
        )
    
    elif query.data == "help":
        help_text = """<b>🤖 Quick Help</b>

<b>Button Functions:</b>
🔄 Refresh - Update gas prices
📊 History - View price trends (coming soon)
⏰ Set Alert - Create price alerts (coming soon)
ℹ️ Help - Show this message

Use /help for detailed information."""
        
        await query.edit_message_text(
            help_text,
            parse_mode='HTML',
            reply_markup=create_keyboard()
        )

def main():
    """Start the bot"""
    # Validate environment variables
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in .env file")
        return
    
    if not ETHERSCAN_API_KEY:
        print("❌ Error: ETHERSCAN_API_KEY not found in .env file")
        return
    
    print("🤖 Starting Ethereum Gas Tracker Bot...")
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("gas", gas_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start bot
    print("✅ Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()