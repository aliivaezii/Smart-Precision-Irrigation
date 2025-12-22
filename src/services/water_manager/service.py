import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'common'))

from MyMQTT import MyMQTT
import time
import requests
import json


class WaterManager:
    """Controller following Controller.py pattern."""
    
    def __init__(self, catalogue_url):
        # 1. Bootstrap: Get config from Catalogue
        print(f"[WaterManager] Fetching config from {catalogue_url}...")
        res = requests.get(catalogue_url)
        data = res.json()
        
        self.broker = data['broker']['address']
        self.port = data['broker']['port']
        self.threshold = data['settings'].get('moisture_threshold', 30.0)
        
        # Find all sensor topics
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
        
        # Memory for latest values (like Controller.py)
        self.memory = {}
        self.rain_alert = False

    def notify(self, topic, payload):
        """Callback when MQTT message received."""
        try:
            data = json.loads(payload)
        except:
            return
            
        # Handle weather alerts
        if topic == 'weather/alert':
            if data.get('status') == 'ACTIVE':
                self.rain_alert = True
                print("[WaterManager] Rain alert ACTIVE - irrigation suspended")
            else:
                self.rain_alert = False
                print("[WaterManager] Rain alert cleared")
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
        """Decision logic: irrigate if moisture < threshold AND no rain."""
        needs_water = moisture < self.threshold
        
        if needs_water and not self.rain_alert:
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
        
        else:
            print(f"[WaterManager] Moisture OK ({moisture}%) - no action needed")

    def run(self):
        """Subscribe to topics and run forever."""
        # Subscribe to all sensor topics
        for topic in self.sensor_topics.keys():
            self.client.subscribe(topic, qos=0)
        
        # Subscribe to weather alerts
        self.client.subscribe('weather/alert', qos=1)
        
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
