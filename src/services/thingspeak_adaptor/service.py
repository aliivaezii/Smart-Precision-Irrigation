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
    Uploads soil moisture, temperature, and water needed to ThingSpeak.
    
    CONFIGURATION:
    - Field 1: Soil Moisture
    - Field 2: Temperature
    - Field 3: Water Needed (Liters)
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
        # UPDATED: 'water_needed' is now mapped to field3
        self.field_map = {
            'soil_moisture': 'field1',
            'temperature': 'field2',
            'water_needed': 'field3',  # <--- Target for Water Needed
            'water_liters': 'field3'   # (Optional) Actual usage also maps here if needed
        }
        
        if not self.api_key:
            print("[ThingSpeak] WARNING: No API key configured!")
        
        print(f"[ThingSpeak] Channel: {self.channel_id}")
        print(f"[ThingSpeak] Field mapping: {self.field_map}")
        
        # Topics
        self.topic_resource = data.get('topics', {}).get('resource_usage', 'smart_irrigation/irrigation/usage')
        self.topic_water_needed = "smart_irrigation/farm/field_1/water_needed"
        
        # Find sensor topics ONLY for Field 1
        self.sensor_topics = []
        for d in data['devices']:
            if d['type'] == 'sensor':
                if 'field_1' in d['id']:
                    for topic in d['topics']['publish']:
                        self.sensor_topics.append(topic)
        
        print(f"[ThingSpeak] Found {len(self.sensor_topics)} sensor topics for Field 1")
        
        # Start MQTT
        self.client = MyMQTT('thingspeak_adaptor', self.broker, self.port, notifier=self)
        self.client.start()
        time.sleep(1)
        
        self.last_update = 0
        self.buffer = {}

    def notify(self, topic, payload):
        """Callback when MQTT message received."""
        try:
            data = json.loads(payload)
        except:
            return
        
        # --- 1. FILTERING LOGIC ---
        
        # If the message comes from the Water Manager (water_needed), we accept it.
        # The bn for water_manager is usually "water_manager".
        is_water_manager = False
        if isinstance(data, dict) and data.get('bn') == 'water_manager':
            is_water_manager = True
        
        # If it's NOT from water manager, we apply strict field filters
        if not is_water_manager:
            # Reject data from Field 2
            if "field_2" in topic: 
                return
            
            # For resource usage, check the BN inside the SenML list
            if topic == self.topic_resource and isinstance(data, list):
                bn = data[0].get('bn', '')
                if 'field_1' not in bn and 'valve_1' not in bn:
                    return

        # --- 2. DATA EXTRACTION ---
        
        # Case A: SenML List (Sensors & Actuators)
        if isinstance(data, list):
            for measurement in data:
                if 'n' in measurement and 'v' in measurement:
                    name = measurement['n']
                    value = measurement['v']
                    
                    if name in self.field_map:
                        self.buffer[name] = value
                        print(f"[ThingSpeak] Buffered: {name}={value} (Field {self.field_map[name][-1]})")

        # Case B: Single Dict (Water Manager often sends single object)
        elif isinstance(data, dict):
            # Check if it has 'n' and 'v' directly (SenML record)
            if 'n' in data and 'v' in data:
                name = data['n']
                value = data['v']
                if name in self.field_map:
                    self.buffer[name] = value
                    print(f"[ThingSpeak] Buffered: {name}={value} (Field {self.field_map[name][-1]})")
            
            # Fallback for legacy dict format { 'v': { 'soil_moisture': 20 } }
            elif 'v' in data and isinstance(data['v'], dict):
                for key, val in data['v'].items():
                    if key in self.field_map:
                        self.buffer[key] = val
                        
        # --- 3. UPLOAD ---
        self.push_to_cloud()

    def push_to_cloud(self):
        """Push buffered data to ThingSpeak."""
        now = time.time()
        
        # ThingSpeak Free Tier Limit: 15 seconds between updates
        if now - self.last_update < 15:
            return
        
        if not self.buffer:
            return
        
        # Build URL parameters
        params = {'api_key': self.api_key}
        for key, val in self.buffer.items():
            if key in self.field_map:
                field = self.field_map[key]
                params[field] = val
        
        try:
            res = requests.get(self.API_URL, params=params, timeout=10)
            if res.ok:
                print(f"[ThingSpeak] ☁️ Upload Success: {self.buffer}")
                self.last_update = now
                self.buffer.clear()
            else:
                print(f"[ThingSpeak] Upload Failed: {res.text}")
        except Exception as e:
            print(f"[ThingSpeak] Connection Error: {e}")

    def run(self):
        """Subscribe and wait."""
        # 1. Sensors
        for topic in self.sensor_topics:
            self.client.subscribe(topic, qos=0)
            
        # 2. Resource Usage
        self.client.subscribe(self.topic_resource, qos=0)
        
        # 3. Water Needed (Critical)
        self.client.subscribe(self.topic_water_needed, qos=0)
        
        print(f"[ThingSpeak] Monitoring Field 1 & Water Needed on Field 3...")
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
        
