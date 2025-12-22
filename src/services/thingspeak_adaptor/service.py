import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'common'))

from MyMQTT import MyMQTT
import time
import requests
import json


class ThingSpeakAdaptor:
    """ThingSpeak Adaptor following professor's simple pattern."""
    
    API_URL = "https://api.thingspeak.com/update"
    
    def __init__(self, catalogue_url):
        # 1. Bootstrap: Get config from Catalogue
        print(f"[ThingSpeak] Fetching config from {catalogue_url}...")
        res = requests.get(catalogue_url)
        data = res.json()
        
        self.broker = data['broker']['address']
        self.port = data['broker']['port']
        
        # Get ThingSpeak settings
        thingspeak = data.get('thingspeak', {})
        self.api_key = thingspeak.get('write_api_key', '')
        self.channel_id = thingspeak.get('channel_id', '')
        
        # Field mapping: sensor_id -> field number
        self.field_map = thingspeak.get('field_map', {
            'soil_moisture': 'field1',
            'temperature': 'field2'
        })
        
        if not self.api_key:
            print("[ThingSpeak] WARNING: No API key configured!")
        
        print(f"[ThingSpeak] Channel: {self.channel_id}")
        
        # Find sensor topics
        self.sensor_topics = []
        for d in data['devices']:
            if d['type'] == 'sensor':
                for topic in d['topics']['publish']:
                    self.sensor_topics.append(topic)
        
        print(f"[ThingSpeak] Found {len(self.sensor_topics)} sensor topics")
        
        # 2. Start MQTT with callback
        self.client = MyMQTT('thingspeak_adaptor', self.broker, self.port, notifier=self)
        self.client.start()
        time.sleep(1)
        
        # Buffer for rate limiting (ThingSpeak: 15s between updates)
        self.last_update = 0
        self.buffer = {}

    def notify(self, topic, payload):
        """Callback when MQTT message received."""
        try:
            data = json.loads(payload)
        except:
            return
        
        # Extract sensor values from SenML format
        if 'v' in data:
            values = data['v']
            if isinstance(values, dict):
                # Buffer the values
                for key, val in values.items():
                    self.buffer[key] = val
                
                # Push to ThingSpeak (rate limited)
                self.push_to_cloud()

    def push_to_cloud(self):
        """Push buffered data to ThingSpeak (15s rate limit)."""
        now = time.time()
        
        # ThingSpeak rate limit: 15 seconds
        if now - self.last_update < 15:
            return
        
        if not self.buffer:
            return
        
        # Build request params
        params = {'api_key': self.api_key}
        
        for key, val in self.buffer.items():
            if key in self.field_map:
                field = self.field_map[key]
                params[field] = val
        
        # Send to ThingSpeak
        try:
            res = requests.get(self.API_URL, params=params, timeout=10)
            if res.ok and res.text != '0':
                print(f"[ThingSpeak] Updated: {self.buffer}")
                self.last_update = now
                self.buffer.clear()
            else:
                print(f"[ThingSpeak] Failed: {res.text}")
        except Exception as e:
            print(f"[ThingSpeak] Error: {e}")

    def run(self):
        """Subscribe to sensor topics and run forever."""
        for topic in self.sensor_topics:
            self.client.subscribe(topic, qos=0)
            print(f"[ThingSpeak] Subscribed to {topic}")
        
        print("[ThingSpeak] Running... forwarding sensor data to cloud")
        
        while True:
            time.sleep(1)

    def stop(self):
        self.client.stop()


if __name__ == '__main__':
    catalogue_url = 'http://localhost:8080/'
    
    adaptor = ThingSpeakAdaptor(catalogue_url)
    try:
        adaptor.run()
    except KeyboardInterrupt:
        adaptor.stop()
        print("[ThingSpeak] Stopped")
