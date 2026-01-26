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
    
    Subscribes to sensor and resource usage topics for Field 1 only.
    Uploads soil moisture, temperature, and water usage to ThingSpeak.
    
    Note: Simplified to Field 1 only due to ThingSpeak channel limitations.
    """
    
    API_URL = "https://api.thingspeak.com/update"
    
    def __init__(self, catalogue_url):
        self.catalogue_url = catalogue_url
        
        print(f"[ThingSpeak] Fetching config from {catalogue_url}...")
        res = requests.get(catalogue_url)
        data = res.json()
        
        self.broker = data['broker']['address']
        self.port = data['broker']['port']
        
        thingspeak = data.get('thingspeak', {})
        self.api_key = thingspeak.get('write_api_key', '')
        self.channel_id = thingspeak.get('channel_id', '')
        
        self.field_map = thingspeak.get('field_map', {
            'soil_moisture': 'field1',
            'temperature': 'field2',
            'water_liters': 'field3',
            'water_needed': 'field4'
        })
        
        if not self.api_key:
            print("[ThingSpeak] WARNING: No API key configured!")
        
        print(f"[ThingSpeak] Channel: {self.channel_id}")
        print(f"[ThingSpeak] Field mapping: {self.field_map}")
        
        topics_config = data.get('topics', {})
        self.topic_resource = topics_config.get('resource_usage', 'smart_irrigation/irrigation/usage')
        
        self.topic_water_needed = "smart_irrigation/farm/field_1/water_needed"
        
        project_info = data.get('project_info', {})
        self.topic_prefix = project_info.get('topic_prefix', 'smart_irrigation')
        
        # Wildcard topic for ALL field_1 sensor data
        # This ensures we get data even if devices register after startup
        self.wildcard_topic = f"{self.topic_prefix}/farm/garden_1/field_1/#"
        
        print(f"[ThingSpeak] Using wildcard topic: {self.wildcard_topic}")
        
        self.client = MyMQTT('thingspeak_adaptor', self.broker, self.port, notifier=self)
        self.client.start()
        time.sleep(1)
        
        self.last_update = 0
        self.buffer = {}

    def notify(self, topic, payload):
        """Callback when MQTT message received."""
        data = json.loads(payload)
        
        # Filter: Only process Field 1 data
        if 'field_2' in topic:
            return
        
        # For resource usage, check if it's from valve_1
        if topic == self.topic_resource:
            if not self.is_field_1_resource(data):
                return
        

        self.process_message(data)
        self.push_to_cloud()

    def is_field_1_resource(self, data):
        """Check if resource data is from Field 1."""
        if isinstance(data, list) and len(data) > 0:
            bn = data[0].get('bn', '')
            if 'valve_1' in bn or 'field_1' in bn:
                return True
        return False

    def process_message(self, data):
        """Process SenML message and buffer values."""
        # Handle SenML format (list of measurements)
        if isinstance(data, list):
            for measurement in data:
                name = measurement.get('n', '')
                value = measurement.get('v', None)
                self.buffer_value(name, value)
            return
        
        # Handle single dict format (from Water Manager)
        if isinstance(data, dict):
            name = data.get('n', '')
            value = data.get('v', None)
            self.buffer_value(name, value)

    def buffer_value(self, name, value):
        """Buffer a value if it's in our field map."""
        if name and value is not None:
            if name in self.field_map:
                self.buffer[name] = value
                print(f"[ThingSpeak] Buffered: {name}={value}")

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
        
        self.client.subscribe(self.wildcard_topic, qos=0)
        print(f"[ThingSpeak] Subscribed to: {self.wildcard_topic}")
        
        self.client.subscribe(self.topic_resource, qos=0)
        print(f"[ThingSpeak] Subscribed to resource: {self.topic_resource}")
        
        self.client.subscribe(self.topic_water_needed, qos=0)
        print(f"[ThingSpeak] Subscribed to water_needed: {self.topic_water_needed}")
        
        print("[ThingSpeak] Running...")
        while True:
            time.sleep(1)

    def stop(self):
        """Stop the adaptor."""
        self.client.stop()
        print("[ThingSpeak] Stopped")


if __name__ == '__main__':
    catalogue_url = 'http://localhost:8080/'
    
    adaptor = ThingSpeakAdaptor(catalogue_url)
    try:
        adaptor.run()
    except KeyboardInterrupt:
        adaptor.stop()
        print("[ThingSpeak] Stopped")
