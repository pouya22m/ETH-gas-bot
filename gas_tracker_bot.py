"""
Ethereum Gas Tracker Telegram Bot
Main bot file with command handlers and conversation flows
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)

# ============================================================================
# IMPORTS FROM NEW MODULES
# ============================================================================
from config import (
    TELEGRAM_BOT_TOKEN,
    ETHERSCAN_API_KEY,
    ALERT_CHECK_INTERVAL,
    ALERT_CHECK_FIRST_RUN
)
from gas_utils import (
    fetch_gas_data,
    get_eth_price,
    format_gas_message
)
from alerts import (
    AlertManager,
    check_and_notify_alerts,
    get_alert_keyboards
)
# ============================================================================

# Conversation states
WAITING_FOR_ALERT_PRICE = 1


# ============================================================================
# KEYBOARD HELPERS
# ============================================================================
def create_main_keyboard():
    """Create main inline keyboard - NOW INCLUDES ALERT BUTTON"""
    return get_alert_keyboards()['main']


# ============================================================================
# COMMAND HANDLERS
# ============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_message = """👋 <b>Welcome to Ethereum Gas Tracker Bot!</b>

I help you monitor Ethereum gas prices in real-time.

<b>Commands:</b>
/gas - Get current gas prices
/setalert - Set a gas price alert
/myalerts - View your active alerts
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
    message = await update.message.reply_text("⏳ Fetching current gas prices...")
    
    gas_data = fetch_gas_data()
    eth_price = get_eth_price()
    
    gas_message = format_gas_message(gas_data, eth_price)
    keyboard = create_main_keyboard()
    
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
/setalert - Set a gas price alert
/myalerts - View your active alerts
/help - Show this help message

<b>Gas Price Alerts:</b>
Set alerts to be notified when gas drops below your target price. The bot checks gas prices every 5 minutes and will send you a notification when your target is reached.

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


# ============================================================================
# ALERT COMMAND HANDLERS (NEW)
# ============================================================================
async def set_alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setalert command - START CONVERSATION"""
    gas_data = fetch_gas_data()
    current_gas = gas_data.get('ProposeGasPrice', 'N/A') if gas_data else 'N/A'
    
    message = f"""⏰ <b>Set Gas Price Alert</b>

Current gas price: <b>{current_gas} Gwei</b>

Please send me the gas price (in Gwei) you want to be alerted at.

For example:
- Send <code>10</code> to be alerted when gas drops below 10 Gwei
- Send <code>15</code> for 15 Gwei alert

Send /cancel to cancel."""
    
    await update.message.reply_text(message, parse_mode='HTML')
    return WAITING_FOR_ALERT_PRICE


async def receive_alert_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's alert price input - CONTINUE CONVERSATION"""
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    
    try:
        alert_price = float(text)
        
        # Add alert using AlertManager
        result = AlertManager.add_alert(user_id, alert_price)
        
        if not result['success']:
            await update.message.reply_text(
                f"❌ {result['message']}\n\nTry again or send /cancel"
            )
            return WAITING_FOR_ALERT_PRICE
        
        # Get current gas for comparison
        gas_data = fetch_gas_data()
        current_gas = float(gas_data.get('ProposeGasPrice', 0)) if gas_data else 0
        
        status = "🟢 Active" if current_gas > alert_price else "⚠️ Already below target"
        
        message = f"""✅ <b>Alert Set Successfully!</b>

🎯 Target: <b>{alert_price} Gwei</b>
📊 Current: <b>{current_gas:.2f} Gwei</b>
📍 Status: {status}

You'll be notified when gas drops below {alert_price} Gwei!

Use /myalerts to view all your alerts."""
        
        keyboard = get_alert_keyboards()['after_set']
        
        await update.message.reply_text(message, parse_mode='HTML', reply_markup=keyboard)
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input. Please enter a number.\n\nExample: <code>15</code>\n\nOr send /cancel",
            parse_mode='HTML'
        )
        return WAITING_FOR_ALERT_PRICE


async def cancel_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel alert setup - END CONVERSATION"""
    await update.message.reply_text(
        "❌ Alert setup cancelled.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⛽ Check Gas", callback_data="refresh")
        ]])
    )
    return ConversationHandler.END


async def view_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /myalerts command"""
    user_id = update.message.from_user.id
    
    if not AlertManager.has_alerts(user_id):
        keyboard = get_alert_keyboards()['no_alerts']
        await update.message.reply_text(
            AlertManager.format_alerts_message(user_id, 0),
            parse_mode='HTML',
            reply_markup=keyboard
        )
        return
    
    gas_data = fetch_gas_data()
    current_gas = float(gas_data.get('ProposeGasPrice', 0)) if gas_data else 0
    
    alerts_text = AlertManager.format_alerts_message(user_id, current_gas)
    keyboard = get_alert_keyboards()['alerts_view']
    
    await update.message.reply_text(
        alerts_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )


# ============================================================================
# BUTTON CALLBACK HANDLERS
# ============================================================================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "refresh":
        await query.edit_message_text("⏳ Fetching latest gas prices...")
        
        gas_data = fetch_gas_data()
        eth_price = get_eth_price()
        
        gas_message = format_gas_message(gas_data, eth_price)
        keyboard = create_main_keyboard()
        
        await query.edit_message_text(
            gas_message,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    
    # ========================================================================
    # ALERT-RELATED CALLBACKS (NEW)
    # ========================================================================
    elif query.data == "set_alert":
        gas_data = fetch_gas_data()
        current_gas = gas_data.get('ProposeGasPrice', 'N/A') if gas_data else 'N/A'
        
        message = f"""⏰ <b>Set Gas Price Alert</b>

Current gas price: <b>{current_gas} Gwei</b>

Please send me the gas price (in Gwei) you want to be alerted at.

For example:
- Send <code>10</code> to be alerted when gas drops below 10 Gwei
- Send <code>15</code> for 15 Gwei alert

Send /cancel to cancel."""
        
        await query.edit_message_text(message, parse_mode='HTML')
    
    elif query.data == "view_alerts":
        user_id = query.from_user.id
        
        if not AlertManager.has_alerts(user_id):
            keyboard = get_alert_keyboards()['no_alerts']
            await query.edit_message_text(
                AlertManager.format_alerts_message(user_id, 0),
                parse_mode='HTML',
                reply_markup=keyboard
            )
            return
        
        gas_data = fetch_gas_data()
        current_gas = float(gas_data.get('ProposeGasPrice', 0)) if gas_data else 0
        
        alerts_text = AlertManager.format_alerts_message(user_id, current_gas)
        keyboard = get_alert_keyboards()['alerts_view']
        
        await query.edit_message_text(
            alerts_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    
    elif query.data == "clear_alerts":
        user_id = query.from_user.id
        count = AlertManager.clear_user_alerts(user_id)
        
        message = f"✅ Cleared {count} alert(s) successfully!" if count > 0 else "No alerts to clear."
        
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("⛽ Check Gas", callback_data="refresh")
        ]])
        
        await query.edit_message_text(message, reply_markup=keyboard)
    # ========================================================================
    
    elif query.data == "help":
        help_text = """<b>🤖 Quick Help</b>

<b>Button Functions:</b>
🔄 Refresh - Update gas prices
⏰ Set Alert - Create price alerts
📋 My Alerts - View your alerts
ℹ️ Help - Show this message

<b>Commands:</b>
/gas - Get current prices
/setalert - Set alert
/myalerts - View alerts

Use /help for detailed information."""
        
        await query.edit_message_text(
            help_text,
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )


# ============================================================================
# MAIN FUNCTION
# ============================================================================
def main():
    """Start the bot"""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in .env file")
        return
    
    if not ETHERSCAN_API_KEY:
        print("❌ Error: ETHERSCAN_API_KEY not found in .env file")
        return
    
    print("🤖 Starting Ethereum Gas Tracker Bot...")
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # ========================================================================
    # CONVERSATION HANDLER FOR ALERTS (NEW)
    # ========================================================================
    alert_conversation = ConversationHandler(
        entry_points=[CommandHandler("setalert", set_alert_command)],
        states={
            WAITING_FOR_ALERT_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_alert_price)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_alert)]
    )
    # ========================================================================
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("gas", gas_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # ========================================================================
    # ADD ALERT HANDLERS (NEW)
    # ========================================================================
    application.add_handler(CommandHandler("myalerts", view_alerts_command))
    application.add_handler(alert_conversation)
    # ========================================================================
    
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # ========================================================================
    # ADD BACKGROUND JOB FOR ALERT CHECKING (NEW)
    # ========================================================================
    job_queue = application.job_queue
    job_queue.run_repeating(
        check_and_notify_alerts,
        interval=ALERT_CHECK_INTERVAL,
        first=ALERT_CHECK_FIRST_RUN
    )
    print(f"✅ Alert checker scheduled (every {ALERT_CHECK_INTERVAL}s)")
    # ========================================================================
    
    print("✅ Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()