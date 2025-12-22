import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'common'))

from MyMQTT import MyMQTT
import time
import requests
import json


class TelegramBot:
    """Telegram Bot following professor's simple pattern."""
    
    def __init__(self, catalogue_url):
        # 1. Bootstrap: Get config from Catalogue
        print(f"[TelegramBot] Fetching config from {catalogue_url}...")
        res = requests.get(catalogue_url)
        data = res.json()
        
        self.broker = data['broker']['address']
        self.port = data['broker']['port']
        
        # Get telegram settings
        telegram = data.get('telegram', {})
        self.token = telegram.get('token', '')
        self.chat_ids = telegram.get('chat_ids', [])
        
        if not self.token:
            print("[TelegramBot] WARNING: No token configured!")
        
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
        print(f"[TelegramBot] Configured with {len(self.chat_ids)} chat(s)")
        
        # 2. Start MQTT with callback
        self.client = MyMQTT('telegram_bot', self.broker, self.port, notifier=self)
        self.client.start()
        time.sleep(1)

    def notify(self, topic, payload):
        """Callback when MQTT message received."""
        try:
            data = json.loads(payload)
        except:
            return
        
        # Handle weather alerts
        if topic == 'weather/alert':
            status = data.get('status', '')
            rain_mm = data.get('precipitation_mm', 0)
            
            if status == 'ACTIVE':
                msg = f"🌧️ RAIN ALERT!\nExpected: {rain_mm}mm\nIrrigation suspended."
            else:
                msg = f"☀️ Rain alert cleared.\nIrrigation resumed."
            
            self.send_message(msg)
        
        # Handle irrigation commands
        elif 'command' in data:
            cmd = data.get('command', '')
            if cmd == 'OPEN':
                duration = data.get('duration', 0)
                msg = f"💧 Irrigation started!\nDuration: {duration}s"
                self.send_message(msg)

    def send_message(self, text):
        """Send message to all configured chats."""
        for chat_id in self.chat_ids:
            url = f"{self.base_url}/sendMessage"
            params = {
                'chat_id': chat_id,
                'text': text
            }
            try:
                res = requests.post(url, data=params, timeout=10)
                if res.ok:
                    print(f"[TelegramBot] Sent to {chat_id}: {text[:30]}...")
                else:
                    print(f"[TelegramBot] Failed to send: {res.text}")
            except Exception as e:
                print(f"[TelegramBot] Error: {e}")

    def run(self):
        """Subscribe to topics and run forever."""
        # Subscribe to weather alerts
        self.client.subscribe('weather/alert', qos=1)
        
        # Subscribe to irrigation commands (all valves)
        self.client.subscribe('irrigation/+/command', qos=0)
        
        print("[TelegramBot] Running... waiting for alerts")
        
        while True:
            time.sleep(1)

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
