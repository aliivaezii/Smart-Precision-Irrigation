import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'common'))

from MyMQTT import MyMQTT
import time
import requests
import json


class ThingSpeakAdaptor:
    """
    ThingSpeak Adaptor - Cloud Data Upload Service
    
    Subscribes to sensor and resource usage topics.
    Uploads soil moisture, temperature, water usage, and energy consumption to ThingSpeak.
    """
    
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
        
        # Field mapping: data_key -> field number
        self.field_map = thingspeak.get('field_map', {
            'soil_moisture': 'field1',
            'temperature': 'field2',
            'water_liters': 'field3',
            'energy_kwh': 'field4'
        })
        
        if not self.api_key:
            print("[ThingSpeak] WARNING: No API key configured!")
        
        print(f"[ThingSpeak] Channel: {self.channel_id}")
        print(f"[ThingSpeak] Field mapping: {self.field_map}")
        
        # Get resource usage topic from config
        topics_config = data.get('topics', {})
        self.topic_resource = topics_config.get('resource_usage', 'smart_irrigation/irrigation/usage')
        
        # Find sensor topics
        self.sensor_topics = []
        for d in data['devices']:
            if d['type'] == 'sensor':
                for topic in d['topics']['publish']:
                    self.sensor_topics.append(topic)
        
        print(f"[ThingSpeak] Found {len(self.sensor_topics)} sensor topics")
        
        # Start MQTT
        self.client = MyMQTT('thingspeak_adaptor', self.broker, self.port, notifier=self)
        self.client.start()
        time.sleep(1)
        
        # Buffer for rate limiting
        self.last_update = 0
        self.buffer = {}

    def notify(self, topic, payload):
        """Callback when MQTT message received."""
        try:
            data = json.loads(payload)
        except:
            return
        
        # Handle SenML format (list of measurements)
        # Format: [{'bn': '...', 'n': 'soil_moisture', 't': ..., 'v': 25}, ...]
        if isinstance(data, list):
            for measurement in data:
                if 'n' in measurement and 'v' in measurement:
                    name = measurement['n']
                    value = measurement['v']
                    
                    # Map measurement name to field
                    if name in self.field_map:
                        self.buffer[name] = value
                        print(f"[ThingSpeak] Buffered: {name}={value}")
            
            # Push to ThingSpeak (rate limited)
            self.push_to_cloud()
            return
        
        # Fallback: Handle old dict format (backward compatibility)
        if isinstance(data, dict) and 'v' in data:
            values = data['v']
            if isinstance(values, dict):
                for key, val in values.items():
                    if key in self.field_map:
                        self.buffer[key] = val
                self.push_to_cloud()

    def push_to_cloud(self):
        """Push buffered data to ThingSpeak."""
        now = time.time()
        
        # Rate limit: 15 seconds between updates
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
        res = requests.get(self.API_URL, params=params, timeout=10)
        if res.ok:
            print(f"[ThingSpeak] Updated: {self.buffer}")
            self.last_update = now
            self.buffer.clear()
        else:
            print(f"[ThingSpeak] Failed: {res.text}")

    def run(self):
        """Subscribe to topics and run forever."""
        for topic in self.sensor_topics:
            self.client.subscribe(topic, qos=0)
            print(f"[ThingSpeak] Subscribed to sensor: {topic}")
        
        self.client.subscribe(self.topic_resource, qos=0)
        print(f"[ThingSpeak] Subscribed to resource: {self.topic_resource}")
        
        print("[ThingSpeak] Running...")
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
