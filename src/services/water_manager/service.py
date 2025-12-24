import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'common'))

from MyMQTT import MyMQTT
import time
import requests
import json


class WaterManager:
    """
    Water Manager - Irrigation Controller
    
    Subscribes to sensor data and weather alerts.
    Decides when to irrigate based on soil moisture and weather conditions.
    
    All MQTT topics are dynamically loaded from Catalogue.
    """
    
    def __init__(self, catalogue_url):
        # 1. Bootstrap: Get config from Catalogue
        print(f"[WaterManager] Fetching config from {catalogue_url}...")
        res = requests.get(catalogue_url)
        data = res.json()
        
        # Get broker info
        self.broker = data['broker']['address']
        self.port = data['broker']['port']
        
        # Get settings
        settings = data.get('settings', {})
        self.moisture_threshold = settings.get('moisture_threshold', 30.0)
        
        # Get MQTT topics from config (NO HARDCODING!)
        topics = data.get('topics', {})
        self.topic_weather_alert = topics.get('weather_alert', 'weather/alert')
        self.topic_frost_alert = topics.get('frost_alert', 'weather/frost')
        
        print(f"[WaterManager] Moisture threshold: {self.moisture_threshold}%")
        print(f"[WaterManager] Alert topics: rain={self.topic_weather_alert}, frost={self.topic_frost_alert}")
        
        # Find all sensor and actuator topics from device list
        self.sensor_topics = {}
        self.actuator_topics = {}
        
        for d in data['devices']:
            if d['type'] == 'sensor':
                for topic in d['topics']['publish']:
                    self.sensor_topics[topic] = d['id']
            elif d['type'] == 'actuator':
                # Map field to valve command topic
                valve_id = d['id']
                field_num = valve_id.split('_')[-1]
                self.actuator_topics[f'field_{field_num}'] = d['topics']['subscribe'][0]
        
        print(f"[WaterManager] Found {len(self.sensor_topics)} sensor topics")
        print(f"[WaterManager] Found {len(self.actuator_topics)} actuators")
        
        # 2. Start MQTT with callback
        self.client = MyMQTT('water_manager', self.broker, self.port, notifier=self)
        self.client.start()
        time.sleep(1)
        
        # Memory for latest values
        self.memory = {}
        self.rain_alert = False
        self.frost_alert = False

    def notify(self, topic, payload):
        """Callback when MQTT message received."""
        try:
            data = json.loads(payload)
        except:
            return
        
        # Handle weather alerts (rain)
        if topic == self.topic_weather_alert:
            if data.get('status') == 'ACTIVE':
                self.rain_alert = True
                print("[WaterManager] Rain alert ACTIVE - irrigation suspended")
            else:
                self.rain_alert = False
                print("[WaterManager] Rain alert cleared")
            return
        
        # Handle frost alerts
        if topic == self.topic_frost_alert:
            if data.get('status') == 'ACTIVE':
                self.frost_alert = True
                temp = data.get('value', 'N/A')
                print(f"[WaterManager] Frost alert ACTIVE ({temp}°C) - irrigation suspended")
            else:
                self.frost_alert = False
                print("[WaterManager] Frost alert cleared")
            return
        
        # Handle sensor data
        if 'v' in data and 'soil_moisture' in data['v']:
            device_id = data.get('bn', 'unknown')
            moisture = data['v']['soil_moisture']
            self.memory[device_id] = moisture
            print(f"[WaterManager] Received: {device_id} -> moisture={moisture}%")
            
            # Evaluate irrigation
            self.evaluate(device_id, moisture)

    def evaluate(self, device_id, moisture):
        """Decision logic: irrigate if moisture < threshold AND no weather alerts."""
        needs_water = moisture < self.moisture_threshold
        weather_ok = not self.rain_alert and not self.frost_alert
        
        if needs_water and weather_ok:
            # Find field from device_id (e.g., sensor_node_field_1 -> field_1)
            parts = device_id.split('_')
            if len(parts) >= 3:
                field_id = f"{parts[-2]}_{parts[-1]}"
            else:
                field_id = None
            
            print(f"[WaterManager] LOW MOISTURE ({moisture}%) - Starting irrigation for {field_id}")
            
            # Publish command to valve
            if field_id in self.actuator_topics:
                cmd = {'command': 'OPEN', 'duration': 300}
                self.client.publish(self.actuator_topics[field_id], json.dumps(cmd))
                print(f"[WaterManager] Sent OPEN command to {self.actuator_topics[field_id]}")
        
        elif needs_water and self.rain_alert:
            print(f"[WaterManager] Low moisture but rain expected - SKIPPING irrigation")
        
        elif needs_water and self.frost_alert:
            print(f"[WaterManager] Low moisture but frost detected - SKIPPING irrigation")
        
        else:
            print(f"[WaterManager] Moisture OK ({moisture}%) - no action needed")

    def run(self):
        """Subscribe to topics and run forever."""
        # Subscribe to all sensor topics
        for topic in self.sensor_topics.keys():
            self.client.subscribe(topic, qos=0)
        
        # Subscribe to weather alerts
        self.client.subscribe(self.topic_weather_alert, qos=1)
        self.client.subscribe(self.topic_frost_alert, qos=1)
        
        print("[WaterManager] Running... waiting for sensor data")
        
        while True:
            time.sleep(1)

    def stop(self):
        self.client.stop()


if __name__ == '__main__':
    catalogue_url = 'http://localhost:8080/'
    
    manager = WaterManager(catalogue_url)
    try:
        manager.run()
    except KeyboardInterrupt:
        manager.stop()
        print("[WaterManager] Stopped")
