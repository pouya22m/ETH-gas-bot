from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from gas_utils import fetch_gas_data, get_eth_price, calculate_tx_cost
from config import MIN_ALERT_PRICE, MAX_ALERT_PRICE, MAX_ALERTS_PER_USER, GAS_LIMITS


# In-memory storage for alerts
# In production, replace with database (SQLite, PostgreSQL, etc.)
user_alerts = {}


class AlertManager:
    """Manages user gas price alerts"""
    
    @staticmethod
    def add_alert(user_id: int, target_price: float) -> dict:
        """
        Add a new alert for a user
        
        Args:
            user_id: Telegram user ID
            target_price: Target gas price in Gwei
            
        Returns:
            dict: Result with success status and message
        """
        # Validate price
        if target_price < MIN_ALERT_PRICE or target_price > MAX_ALERT_PRICE:
            return {
                'success': False,
                'message': f"Price must be between {MIN_ALERT_PRICE} and {MAX_ALERT_PRICE} Gwei"
            }
        
        # Check alert limit
        if user_id in user_alerts and len(user_alerts[user_id]) >= MAX_ALERTS_PER_USER:
            return {
                'success': False,
                'message': f"You can only have {MAX_ALERTS_PER_USER} active alerts. Please delete some first."
            }
        
        # Create alert
        if user_id not in user_alerts:
            user_alerts[user_id] = []
        
        alert = {
            'price': target_price,
            'created_at': datetime.now(),
            'triggered': False
        }
        
        user_alerts[user_id].append(alert)
        
        return {
            'success': True,
            'message': f"Alert set for {target_price} Gwei",
            'alert': alert
        }
    
    @staticmethod
    def get_user_alerts(user_id: int) -> list:
        """Get all alerts for a user"""
        return user_alerts.get(user_id, [])
    
    @staticmethod
    def clear_user_alerts(user_id: int) -> int:
        """Clear all alerts for a user. Returns count of cleared alerts."""
        if user_id in user_alerts:
            count = len(user_alerts[user_id])
            user_alerts[user_id] = []
            return count
        return 0
    
    @staticmethod
    def delete_alert(user_id: int, alert_index: int) -> bool:
        """Delete a specific alert by index"""
        if user_id in user_alerts and 0 <= alert_index < len(user_alerts[user_id]):
            user_alerts[user_id].pop(alert_index)
            return True
        return False
    
    @staticmethod
    def has_alerts(user_id: int) -> bool:
        """Check if user has any alerts"""
        return user_id in user_alerts and len(user_alerts[user_id]) > 0
    
    @staticmethod
    def format_alerts_message(user_id: int, current_gas: float) -> str:
        """Format user's alerts into a readable message"""
        alerts = AlertManager.get_user_alerts(user_id)
        
        if not alerts:
            return """📋 <b>Your Gas Alerts</b>

You don't have any active alerts.

Use /setalert to create one!"""
        
        message = f"📋 <b>Your Gas Alerts</b>\n\n📊 Current Gas: <b>{current_gas:.2f} Gwei</b>\n\n"
        
        for i, alert in enumerate(alerts, 1):
            price = alert['price']
            
            if alert['triggered']:
                status = "✅ Triggered"
            elif current_gas > price:
                status = "🟢 Active"
            else:
                status = "⚠️ Below target"
            
            created = alert['created_at'].strftime('%Y-%m-%d %H:%M')
            
            message += f"<b>Alert #{i}</b>\n"
            message += f"🎯 Target: {price} Gwei\n"
            message += f"📍 Status: {status}\n"
            message += f"📅 Created: {created}\n\n"
        
        return message


async def check_and_notify_alerts(context: ContextTypes.DEFAULT_TYPE):
    """
    Background job to check alerts and send notifications
    This function is called periodically by the job queue
    """
    # Fetch current gas data
    gas_data = fetch_gas_data()
    if not gas_data:
        print("Failed to fetch gas data for alert checking")
        return
    
    current_gas = float(gas_data.get('ProposeGasPrice', 0))
    if current_gas == 0:
        print("Invalid gas price received")
        return
    
    eth_price = get_eth_price()
    
    print(f"Checking alerts... Current gas: {current_gas:.2f} Gwei")
    
    # Check each user's alerts
    notifications_sent = 0
    
    for user_id, alerts in user_alerts.items():
        for alert in alerts:
            # Check if alert should trigger
            if not alert['triggered'] and current_gas <= alert['price']:
                # Mark as triggered
                alert['triggered'] = True
                
                # Calculate sample costs
                eth_transfer = calculate_tx_cost(current_gas, GAS_LIMITS['eth_transfer'], eth_price)
                token_swap = calculate_tx_cost(current_gas, GAS_LIMITS['token_swap'], eth_price)
                
                # Create notification message
                message = f"""🔔 <b>Gas Alert Triggered!</b>

🎯 Your target: <b>{alert['price']} Gwei</b>
📊 Current gas: <b>{current_gas:.2f} Gwei</b>

💰 <b>Sample Costs:</b>
- ETH Transfer: ${eth_transfer:.2f}
- Token Swap: ${token_swap:.2f}

⚡ Great time to make your transaction!

Use /gas to see full details."""
                
                keyboard = [[InlineKeyboardButton("⛽ View Gas Prices", callback_data="refresh")]]
                
                # Send notification
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    notifications_sent += 1
                    print(f"Alert notification sent to user {user_id}")
                except Exception as e:
                    print(f"Error sending alert to user {user_id}: {e}")
    
    if notifications_sent > 0:
        print(f"Sent {notifications_sent} alert notification(s)")


def get_alert_keyboards():
    """Get keyboard layouts for alert-related messages"""
    return {
        'main': InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
                InlineKeyboardButton("⏰ Set Alert", callback_data="set_alert")
            ],
            [
                InlineKeyboardButton("📋 My Alerts", callback_data="view_alerts"),
                InlineKeyboardButton("ℹ️ Help", callback_data="help")
            ]
        ]),
        
        'alerts_view': InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ Clear All Alerts", callback_data="clear_alerts")],
            [InlineKeyboardButton("⏰ Add New Alert", callback_data="set_alert")],
            [InlineKeyboardButton("🔙 Back", callback_data="refresh")]
        ]),
        
        'no_alerts': InlineKeyboardMarkup([
            [InlineKeyboardButton("⏰ Set Alert", callback_data="set_alert")]
        ]),
        
        'after_set': InlineKeyboardMarkup([
            [InlineKeyboardButton("⛽ Check Gas Now", callback_data="refresh")]
        ])
    }