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


class TelegramBot():
    """Telegram Bot for IoT Control and Monitoring."""
    
    def __init__(self, catalogue_url):
        self.catalogue_url = catalogue_url
        self.sensor_readings = {} # Cache for last known sensor values
        self.device_topics = {}   # Map device_id -> topic for sending commands

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
        
        # Get topics from Catalogue
        topics_config = data.get('topics', {})
        self.topic_weather_alert = topics_config.get('weather_alert', 'smart_irrigation/weather/alert')
        self.topic_frost_alert = topics_config.get('frost_alert', 'smart_irrigation/weather/frost')
        self.topic_irrigation_cmd = topics_config.get('irrigation_command', 'smart_irrigation/irrigation/+/command')
        self.topic_valve_status = topics_config.get('valve_status', 'smart_irrigation/irrigation/+/status')
        
        # Telegram settings
        telegram = data.get('telegram', {})
        self.token = telegram.get('token', '')
        self.chat_ids = telegram.get('chat_ids', [])
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
        # 2. Setup Bot
        self.bot = telepot.Bot(self.token)
        self.callback_dict = {'chat':self.on_chat_message, 'callback_query':self.on_callback_query}
        MessageLoop(self.bot, self.callback_dict).run_as_thread()

        if not self.token:
            print("[TelegramBot] WARNING: No token configured!")
        
        # 3. Start MQTT
        self.client = MyMQTT('telegram_bot', self.broker, self.port, notifier=self)
        self.client.start()
        time.sleep(1)
        
        # 4. Subscribe to System Topics & Sensors
        self.setup_subscriptions()

    def setup_subscriptions(self):
        """Fetch devices from catalogue and subscribe to their topics."""
        try:
            url = self.catalogue_url
            if not url.endswith('/'): url += '/'
            url += 'devices'
            
            res = requests.get(url)
            devices = res.json()
            
            # Standard system subscriptions (from Catalogue config)
            self.client.subscribe(self.topic_weather_alert, qos=1)
            self.client.subscribe(self.topic_frost_alert, qos=1)
            self.client.subscribe(self.topic_valve_status, qos=1)
            self.client.subscribe(self.topic_irrigation_cmd, qos=0)  # Monitor commands
            print(f"[TelegramBot] Subscribed to: {self.topic_weather_alert}, {self.topic_frost_alert}, {self.topic_valve_status}")
            
            # Dynamic device subscriptions
            for dev in devices:
                d_id = dev.get('id')
                topics = dev.get('topics', {})
                
                # If it's a sensor, subscribe to its publish topic to cache readings
                if dev.get('type') == 'sensor':
                    for t in topics.get('publish', []):
                        self.client.subscribe(t, qos=0)
                        print(f"[Sub] Monitoring sensor {d_id} on {t}")
                        
                # If it's an actuator, save its subscribe topic so we can control it later
                if dev.get('type') == 'actuator':
                    # We assume the first subscribe topic is the command topic
                    cmd_topics = topics.get('subscribe', [])
                    if cmd_topics:
                        self.device_topics[d_id] = cmd_topics[0]
            
        except Exception as e:
            print(f"[TelegramBot] Error setting up subscriptions: {e}")

    def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        
        if chat_id not in self.chat_ids:
            self.chat_ids.append(chat_id)

        if content_type == 'text' and msg['text'] == '/start':
            self.send_main_menu(chat_id)

    def send_main_menu(self, chat_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='View Sensors', callback_data='menu_sensors')],
            [InlineKeyboardButton(text='Control Actuators', callback_data='menu_actuators')],
            [InlineKeyboardButton(text='Refresh System', callback_data='sys_refresh')]
        ])
        self.bot.sendMessage(chat_id, "**Smart Irrigation Control Panel** \nSelect an option:", reply_markup=keyboard, parse_mode='Markdown')

    def on_callback_query(self, msg):
        """Handle navigation and commands."""
        query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')
        
        # --- MENU NAVIGATION ---
        if query_data == 'main_menu':
            # Edit the message to show main menu
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='View Sensors', callback_data='menu_sensors')],
                [InlineKeyboardButton(text='Control Actuators', callback_data='menu_actuators')]
            ])
            self.bot.editMessageText((from_id, msg['message']['message_id']), 
                                     "**Smart Irrigation Control Panel** \nSelect an option:", 
                                     reply_markup=keyboard, parse_mode='Markdown')

        elif query_data == 'menu_sensors':
            self.show_device_list(from_id, msg['message']['message_id'], 'sensor')
            
        elif query_data == 'menu_actuators':
            self.show_device_list(from_id, msg['message']['message_id'], 'actuator')

        # --- DEVICE DETAILS (SENSORS) ---
        elif query_data.startswith('view_'):
            device_id = query_data.split('_')[1]
            self.show_sensor_detail(from_id, msg['message']['message_id'], device_id)
            
        # --- DEVICE CONTROL (ACTUATORS) ---
        elif query_data.startswith('ctrl_'):
            device_id = query_data.split('_')[1]
            self.show_actuator_controls(from_id, msg['message']['message_id'], device_id)

        # --- EXECUTE COMMANDS ---
        elif query_data.startswith('cmd_'):
            # Format: cmd_DEVICEID_ACTION
            parts = query_data.split('_')
            device_id = parts[1]
            action = parts[2] # OPEN or CLOSE
            
            self.send_actuator_command(device_id, action)
            self.bot.answerCallbackQuery(query_id, text=f"Command '{action}' sent to {device_id}")

        elif query_data == 'sys_refresh':
            self.setup_subscriptions()
            self.bot.answerCallbackQuery(query_id, text="System configuration reloaded.")

    def show_device_list(self, chat_id, msg_id, dev_type):
        """Fetch devices and show them as a list of buttons."""
        try:
            url = f"{self.catalogue_url}devices" if self.catalogue_url.endswith('/') else f"{self.catalogue_url}/devices"
            devices = requests.get(url).json()
            
            buttons = []
            for d in devices:
                if d.get('type') == dev_type:
                    name = d.get('name', d['id'])
                    # If sensor, click to view. If actuator, click to control.
                    prefix = "view" if dev_type == 'sensor' else "ctrl"
                    callback = f"{prefix}_{d['id']}"
                    buttons.append([InlineKeyboardButton(text=name, callback_data=callback)])
            
            # Add Back Button
            buttons.append([InlineKeyboardButton(text='Back to Main Menu', callback_data='main_menu')])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            title = "Sensors" if dev_type == 'sensor' else "Actuators"
            self.bot.editMessageText((chat_id, msg_id), f" **Select a {title}:**", reply_markup=keyboard, parse_mode='Markdown')
            
        except Exception as e:
            print(f"Error listing devices: {e}")

    def show_sensor_detail(self, chat_id, msg_id, device_id):
        """Show last reading for a specific sensor."""
        # Get last known data from our local cache
        data = self.sensor_readings.get(device_id)
        
        if data:
            # Handle SenML list format: [{'bn': '...', 'n': 'soil_moisture', 't': ..., 'v': 25}, ...]
            if isinstance(data, list):
                lines = []
                for measurement in data:
                    name = measurement.get('n', 'unknown')
                    val = measurement.get('v', 'N/A')
                    lines.append(f"  {name}: **{val}**")
                timestamp = data[0].get('t', 'Unknown time') if data else 'Unknown'
                readings_text = '\n'.join(lines)
                text = f"📊 **Sensor Status**\n\n`{device_id}`\nTime: {timestamp}\n\n{readings_text}"
            else:
                # Fallback for old dict format
                timestamp = data.get('t', 'Unknown time')
                val = data.get('v', 'N/A')
                unit = data.get('u', '')
                text = f"📊 **Sensor Status**\n\n`{device_id}`\nTime: {timestamp}\nValue: **{val} {unit}**"
        else:
            text = f"📊 **Sensor Status**\n\n`{device_id}`\nNo data received yet."

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🔄 Update', callback_data=f'view_{device_id}')],
            [InlineKeyboardButton(text='⬅️ Back to Sensors', callback_data='menu_sensors')]
        ])
        self.bot.editMessageText((chat_id, msg_id), text, reply_markup=keyboard, parse_mode='Markdown')

    def show_actuator_controls(self, chat_id, msg_id, device_id):
        """Show ON/OFF buttons for an actuator."""
        text = f"**Control Panel**\n\nTarget: `{device_id}`\nSelect action:"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text='Turn ON', callback_data=f'cmd_{device_id}_OPEN'),
                InlineKeyboardButton(text='Turn OFF', callback_data=f'cmd_{device_id}_CLOSE')
            ],
            [InlineKeyboardButton(text='Back to Actuators', callback_data='menu_actuators')]
        ])
        self.bot.editMessageText((chat_id, msg_id), text, reply_markup=keyboard, parse_mode='Markdown')

    def send_actuator_command(self, device_id, action):
        """Publish MQTT command."""
        topic = self.device_topics.get(device_id)
        
        if topic:
            # Construct standard command payload
            payload = {
                "command": action,
                "timestamp": time.time()
            }
            if action == 'OPEN':
                payload["duration"] = 60 # Default duration for safety
                
            self.client.publish(topic, json.dumps(payload))
            print(f"[MQTT] Sent {action} to {topic}")
        else:
            print(f"[Error] No topic found for {device_id}")

    def notify(self, topic, payload):
        """MQTT Callback: Store sensor data or handle alerts."""
        data = json.loads(payload)
        
        # Handle Sensor Data
        if 'soil_moisture' in topic:
            if "field_1" in topic:
                self.sensor_readings["sensor_node_field_1"] = data
            if "field_2" in topic:
                self.sensor_readings["sensor_node_field_2"] = data
            return

        # Handle Rain Alerts
        if topic == self.topic_weather_alert:
            status = data.get('status', '')
            rain_mm = data.get('precipitation_mm', 0)
            if status == 'ACTIVE':
                msg = f"🌧️ RAIN ALERT!\nExpected: {rain_mm}mm\nIrrigation suspended."
            else:
                msg = f"☀️ Rain alert cleared.\nIrrigation resumed."
            self.send_broadcast(msg)
            return

        # Handle Frost Alerts
        if topic == self.topic_frost_alert:
            status = data.get('status', '')
            temp = data.get('value', 'N/A')
            if status == 'ACTIVE':
                msg = f"❄️ FROST ALERT!\nTemperature: {temp}°C\nIrrigation suspended."
            else:
                msg = f"🌡️ Frost alert cleared.\nTemperature: {temp}°C"
            self.send_broadcast(msg)
            return

        # Handle Valve Status Updates
        if '/status' in topic:
            parts = topic.split('/')
            if len(parts) > 2:
                field_name = parts[2]
            else:
                field_name = 'unknown'
            
            valve_status = None
            duration = 0
            water_liters = 0
            
            for m in data:
                if m.get('n') == 'valve_status':
                    valve_status = m.get('v')
                if m.get('n') == 'duration':
                    duration = m.get('v', 0)
                if m.get('n') == 'water_liters':
                    water_liters = m.get('v', 0)
            
            if valve_status == 'OPEN':
                msg = f"💧 Irrigation Started\nField: {field_name}\nDuration: {duration}s"
                self.send_broadcast(msg)
            
            if valve_status == 'CLOSED':
                if water_liters > 0:
                    msg = f"✅ Irrigation Complete\nField: {field_name}\nWater used: {water_liters:.1f}L"
                    self.send_broadcast(msg)

    def send_broadcast(self, text):
        """Send message to all configured chats."""
        for chat_id in self.chat_ids:
            self.bot.sendMessage(chat_id, text)

    def run(self):
        """Main loop."""
        print("[TelegramBot] System running...")
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
