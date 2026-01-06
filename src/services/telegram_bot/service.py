"""
Telegram Bot Service - Alerts and System Status

1. Subscribes to weather/frost alerts via MQTT
2. Sends alert notifications to subscribed users
3. Fetches system status from Status Service via REST (not MQTT)

"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'common'))

import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton

from MyMQTT import MyMQTT
import time
import requests
import json


class TelegramBot:
    """
    Telegram Bot - Alerts and System Status Viewer.
    
    Features:
    - Subscribe to weather/frost alerts
    - View system status (via Status Service REST API)
    """
    
    # URL of the Status Service
    STATUS_SERVICE_URL = "http://localhost:9090"

    def __init__(self, catalogue_url):
        self.catalogue_url = catalogue_url
        self.alert_subscribers = []

        # 1. Bootstrap: Get config from Catalogue
        print(f"[TelegramBot] Fetching config from {catalogue_url}...")
        res = requests.get(catalogue_url)
        data = res.json()
        
        self.broker = data['broker']['address']
        self.port = data['broker']['port']
        
        # Get alert topics from Catalogue
        topics_config = data.get('topics', {})
        self.topic_weather_alert = topics_config.get('weather_alert', 'smart_irrigation/weather/alert')
        self.topic_frost_alert = topics_config.get('frost_alert', 'smart_irrigation/weather/frost')
        
        # Telegram settings
        telegram_config = data.get('telegram', {})
        self.token = telegram_config.get('token', '')
        self.chat_ids = telegram_config.get('chat_ids', [])
        
        if not self.token:
            print("[TelegramBot] WARNING: No token configured!")
        
        print(f"[TelegramBot] Broker: {self.broker}:{self.port}")
        print(f"[TelegramBot] Weather alert topic: {self.topic_weather_alert}")
        print(f"[TelegramBot] Frost alert topic: {self.topic_frost_alert}")
        
        # 2. Setup Telegram Bot
        self.bot = telepot.Bot(self.token)
        callback_handlers = {
            'chat': self.on_chat_message,
            'callback_query': self.on_callback_query
        }
        MessageLoop(self.bot, callback_handlers).run_as_thread()
        
        # 3. Start MQTT (only for alerts)
        self.client = MyMQTT('telegram_bot', self.broker, self.port, notifier=self)
        self.client.start()
        time.sleep(1)
        
        # 4. Subscribe to alert topics only
        self.setup_subscriptions()

    def setup_subscriptions(self):
        """Subscribe ONLY to weather and frost alert topics."""
        print("[TelegramBot] Subscribing to alert topics...")
        self.client.subscribe(self.topic_weather_alert, qos=1)
        self.client.subscribe(self.topic_frost_alert, qos=1)
        print("[TelegramBot] Subscribed to alerts")

    def on_chat_message(self, msg):
        """Handle incoming chat messages."""
        content_type, chat_type, chat_id = telepot.glance(msg)
        
        # Add new users to chat list
        if chat_id not in self.chat_ids:
            self.chat_ids.append(chat_id)
        
        # Handle /start command
        if content_type == 'text':
            if msg['text'] == '/start':
                self.send_main_menu(chat_id)

    def send_main_menu(self, chat_id):
        """Send the main menu with options."""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🔔 Subscribe to Alerts', callback_data='subscribe_alerts')],
            [InlineKeyboardButton(text='📊 View System Status', callback_data='view_status')]
        ])
        
        message = "🌱 **Smart Irrigation Bot**\n\nSelect an option:"
        self.bot.sendMessage(chat_id, message, reply_markup=keyboard, parse_mode='Markdown')

    def on_callback_query(self, msg):
        """Handle button callbacks."""
        query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')
        
        # Handle main menu button
        if query_data == 'main_menu':
            self.send_main_menu(from_id)
            return
        
        # Handle subscribe to alerts
        if query_data == 'subscribe_alerts':
            if from_id not in self.alert_subscribers:
                self.alert_subscribers.append(from_id)
                self.bot.answerCallbackQuery(query_id, text="Subscribed!")
                self.bot.sendMessage(from_id, "✅ **Success!**\nYou will now receive Rain and Frost alerts.", parse_mode='Markdown')
            else:
                self.bot.answerCallbackQuery(query_id, text="Already subscribed.")
            return
        
        # Handle view status
        if query_data == 'view_status':
            self.bot.answerCallbackQuery(query_id, text="Fetching status...")
            self.show_system_status(from_id)
            return

    def show_system_status(self, chat_id):
        """Fetch status from Status Service and display it."""
        # Get status from Status Service
        response = requests.get(self.STATUS_SERVICE_URL, timeout=5)
        
        if response.status_code != 200:
            self.bot.sendMessage(chat_id, "❌ **Error:** Could not contact Status Service.")
            return
        
        data = response.json()
        
        if not data:
            self.bot.sendMessage(chat_id, "ℹ️ No device data available yet.")
            return
        
        # Build status message
        lines = ["🌱 **System Status**\n"]
        
        for device_id, info in data.items():
            # Skip system alerts in status view
            if device_id == 'system_alert':
                continue
            
            payload = info.get('payload', [])
            timestamp = info.get('received_at', 'Unknown')
            
            # Choose icon based on device type
            if 'actuator' in device_id or 'valve' in device_id:
                icon = "⚙️"
            else:
                icon = "📡"
            
            lines.append(f"\n{icon} **`{device_id}`**")
            lines.append(f"   🕒 _Updated: {timestamp}_")
            
            # Parse SenML payload (list format)
            if isinstance(payload, list):
                for item in payload:
                    name = item.get('n', '')
                    value = item.get('v', 'N/A')
                    
                    if 'soil_moisture' in name:
                        lines.append(f"   💧 Moisture: **{value}%**")
                    elif 'temperature' in name:
                        lines.append(f"   🌡️ Temp: **{value}°C**")
                    elif 'valve_status' in name:
                        if value == "OPEN":
                            status_icon = "🟢"
                        else:
                            status_icon = "🔴"
                        lines.append(f"   🚿 Valve: {status_icon} **{value}**")
                    elif 'water_liters' in name:
                        lines.append(f"   🚰 Water Used: **{value}L**")
                    else:
                        lines.append(f"   🔹 {name}: **{value}**")
        
        # Add refresh button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🔄 Refresh', callback_data='view_status')],
            [InlineKeyboardButton(text='⬅️ Back', callback_data='main_menu')]
        ])
        
        final_message = "\n".join(lines)
        self.bot.sendMessage(chat_id, final_message, reply_markup=keyboard, parse_mode='Markdown')

    def notify(self, topic, payload):
        """MQTT Callback: Handle alert messages only."""
        data = json.loads(payload)
        
        # Handle Rain Alert
        if topic == self.topic_weather_alert:
            status = data.get('status', '')
            rain_mm = data.get('precipitation_mm', 0)
            
            if status == 'ACTIVE':
                msg = f"🌧️ **RAIN ALERT!**\nExpected: {rain_mm}mm\nIrrigation suspended."
            else:
                msg = f"☀️ Rain alert cleared.\nIrrigation resumed."
            
            self.send_alert_broadcast(msg)
            return

        # Handle Frost Alert
        if topic == self.topic_frost_alert:
            status = data.get('status', '')
            temp = data.get('value', 'N/A')
            
            if status == 'ACTIVE':
                msg = f"❄️ **FROST ALERT!**\nTemperature: {temp}°C\nIrrigation suspended."
            else:
                msg = f"🌡️ Frost alert cleared.\nTemperature: {temp}°C"
            
            self.send_alert_broadcast(msg)
            return

    def send_alert_broadcast(self, text):
        """Send alert message to all subscribed users."""
        if not self.alert_subscribers:
            print("[TelegramBot] No subscribers for alerts")
            return
        
        for chat_id in self.alert_subscribers:
            self.bot.sendMessage(chat_id, text, parse_mode='Markdown')
        
        print(f"[TelegramBot] Alert sent to {len(self.alert_subscribers)} subscribers")

    def run(self):
        """Main loop."""
        print("[TelegramBot] Running...")
        while True:
            time.sleep(10)

    def stop(self):
        """Stop the bot."""
        self.client.stop()
        print("[TelegramBot] Stopped")


if __name__ == '__main__':
    catalogue_url = 'http://localhost:8080/'
    
    bot = TelegramBot(catalogue_url)
    
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.stop()
        print("[TelegramBot] Shutdown complete")
