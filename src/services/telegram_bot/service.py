import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'common'))
import telepot
import telepot.exception
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton

from MyMQTT import MyMQTT
import time
import requests
import json
import datetime

class TelegramBot():
    """Telegram Bot: Alerts & System Status Viewer"""
    
    # URL of the Status Service (Defaulting to localhost:9090 as per your previous script)
    STATUS_SERVICE_URL = "http://localhost:9090"

    def __init__(self, catalogue_url):
        self.catalogue_url = catalogue_url
        self.alert_subscribers = [] 

        # 1. Bootstrap: Get config from Catalogue
        print(f"[TelegramBot] Fetching config from {catalogue_url}...")
        try:
            res = requests.get(catalogue_url)
            res.raise_for_status()
            data = res.json()
        except Exception as e:
            print(f"CRITICAL: Could not connect to Catalogue: {e}")
            sys.exit(1)
        
        self.broker = data['broker']['address']
        self.port = data['broker']['port']
        
        # Get Alert Topics
        topics_config = data.get('topics', {})
        self.topic_weather_alert = topics_config.get('weather_alert', 'smart_irrigation/weather/alert')
        self.topic_frost_alert = topics_config.get('frost_alert', 'smart_irrigation/weather/frost')
        
        # Telegram settings
        telegram = data.get('telegram', {})
        self.token = telegram.get('token', '')
        self.chat_ids = telegram.get('chat_ids', [])
        
        # 2. Setup Bot
        self.bot = telepot.Bot(self.token)
        self.callback_dict = {'chat':self.on_chat_message, 'callback_query':self.on_callback_query}
        MessageLoop(self.bot, self.callback_dict).run_as_thread()

        if not self.token:
            print("[TelegramBot] WARNING: No token configured!")
        
        # 3. Start MQTT (ONLY for Alerts now)
        self.client = MyMQTT('telegram_bot', self.broker, self.port, notifier=self)
        self.client.start()
        time.sleep(1)
        
        # 4. Subscribe
        self.setup_subscriptions()

    def setup_subscriptions(self):
        """Subscribe ONLY to Weather and Frost alerts."""
        print("[TelegramBot] Subscribing to Alert Topics...")
        self.client.subscribe(self.topic_weather_alert, qos=1)
        self.client.subscribe(self.topic_frost_alert, qos=1)

    def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        if chat_id not in self.chat_ids:
            self.chat_ids.append(chat_id)
        
        if content_type == 'text' and msg['text'] == '/start':
            self.send_main_menu(chat_id)

    def send_main_menu(self, chat_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🔔 Subscribe to Weather Alerts', callback_data='sub_alerts')],
            [InlineKeyboardButton(text='📊 View System Status', callback_data='view_status')]
        ])
        self.bot.sendMessage(chat_id, "**Smart Irrigation Bot** \nSelect an option:", reply_markup=keyboard, parse_mode='Markdown')

    def on_callback_query(self, msg):
        query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')
        
        # --- RETURN TO MAIN MENU ---
        if query_data == 'main_menu':
            self.send_main_menu(from_id)

        # --- OPTION 1: SUBSCRIBE TO ALERTS ---
        elif query_data == 'sub_alerts':
            if from_id not in self.alert_subscribers:
                self.alert_subscribers.append(from_id)
                self.bot.answerCallbackQuery(query_id, text="Subscribed!")
                self.bot.sendMessage(from_id, "✅ **Success!**\nYou will now receive immediate notifications for Rain and Frost.")
            else:
                self.bot.answerCallbackQuery(query_id, text="Already subscribed.")

        # --- OPTION 2: VIEW SYSTEM STATUS (REST API) ---
        elif query_data == 'view_status':
            self.bot.answerCallbackQuery(query_id, text="Fetching status...")
            self.view_system_status(from_id)

    def view_system_status(self, chat_id):
        """Fetch status from Status Service (HTTP) and format it."""
        try:
            # 1. GET Request to Status Service
            response = requests.get(self.STATUS_SERVICE_URL, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                self.bot.sendMessage(chat_id, "ℹ️ System Status is empty. No devices have reported yet.")
                return

            # 2. Format the Output
            msg_lines = ["🌱 **Current System Status** 🌱"]
            
            for device_id, info in data.items():
                # Skip internal system alerts in the status view if desired, or show them
                if device_id == 'system_alert':
                    continue

                payload = info.get('payload', [])
                timestamp = info.get('received_at', 'Unknown')
                
                # Header for each device
                dev_icon = "⚙️" if "actuator" in device_id or "valve" in device_id else "📡"
                msg_lines.append(f"\n{dev_icon} **`{device_id}`**")
                msg_lines.append(f"   🕒 _Updated: {timestamp}_")
                
                # Parse SenML List
                if isinstance(payload, list):
                    for item in payload:
                        n = item.get('n', '')
                        v = item.get('v', 'N/A')
                        u = item.get('u', '') # unit if available
                        
                        # Pretty printing based on variable name
                        if 'soil_moisture' in n:
                            msg_lines.append(f"   💧 Moisture: **{v}%**")
                        elif 'temperature' in n:
                            msg_lines.append(f"   🌡️ Temp: **{v}°C**")
                        elif 'valve_status' in n:
                            status_icon = "🟢" if v == "OPEN" else "🔴"
                            msg_lines.append(f"   🚿 Valve: {status_icon} **{v}**")
                        elif 'water_liters' in n:
                            msg_lines.append(f"   🚰 Water Used: {v}L")
                        elif 'energy' in n:
                            msg_lines.append(f"   ⚡ Energy: {v}kWh")
                        else:
                            msg_lines.append(f"   🔹 {n}: {v} {u}")

            # Add Refresh Button
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='🔄 Refresh', callback_data='view_status')],
                [InlineKeyboardButton(text='⬅️ Back', callback_data='main_menu')]
            ])
            
            final_msg = "\n".join(msg_lines)
            self.bot.sendMessage(chat_id, final_msg, reply_markup=keyboard, parse_mode='Markdown')

        except requests.exceptions.ConnectionError:
            self.bot.sendMessage(chat_id, "❌ **Error:** Could not contact Status Service.\nIs `status_service.py` running?")
        except Exception as e:
            print(f"Error fetching status: {e}")
            self.bot.sendMessage(chat_id, "❌ Error parsing system status.")

    def notify(self, topic, payload):
        """MQTT Callback: ONLY handles alerts now."""
        try:
            data = json.loads(payload)
        except:
            return

        # Handle Rain Alerts
        if topic == self.topic_weather_alert:
            status = data.get('status', '')
            rain_mm = data.get('precipitation_mm', 0)
            if status == 'ACTIVE':
                msg = f"🌧️ **RAIN ALERT!**\nExpected: {rain_mm}mm\nIrrigation suspended."
            else:
                msg = f"☀️ Rain alert cleared.\nIrrigation resumed."
            self.send_alert_broadcast(msg)

        # Handle Frost Alerts
        elif topic == self.topic_frost_alert:
            status = data.get('status', '')
            temp = data.get('value', 'N/A')
            if status == 'ACTIVE':
                msg = f"❄️ **FROST ALERT!**\nTemperature: {temp}°C\nIrrigation suspended."
            else:
                msg = f"🌡️ Frost alert cleared.\nTemperature: {temp}°C"
            self.send_alert_broadcast(msg)

    def send_alert_broadcast(self, text):
        if not self.alert_subscribers:
            return
        for chat_id in self.alert_subscribers:
            try:
                self.bot.sendMessage(chat_id, text, parse_mode='Markdown')
            except:
                pass

    def run(self):
        print("[TelegramBot] Running (Status Mode)...")
        while True:
            time.sleep(10)

    def stop(self):
        self.client.stop()

if __name__ == '__main__':
    catalogue_url = 'http://localhost:8080/'
    
    bot = TelegramBot(catalogue_url)
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.stop()
        print("[TelegramBot] Stopped")
        
