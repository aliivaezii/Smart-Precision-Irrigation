"""
Water Manager - Smart Irrigation Controller

The brain of the Smart Precision Irrigation System.
Subscribes to sensor data and weather alerts via MQTT.
Triggers irrigation when soil moisture falls below threshold,
with duration based on crop type configuration.

Features:
- Moisture-based irrigation triggering
- Weather-aware (skips irrigation during rain/frost alerts)
- Auto-discovery of new devices every 60 seconds
- Crop-specific irrigation durations
"""

import sys
import os
from MyMQTT import MyMQTT
import time
import requests
import json
import threading
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'common'))

class WaterManager:
    """
    Smart Irrigation Controller.
    
    Decision Logic:
    1. If moisture < threshold AND no rain/frost alerts → trigger irrigation
    2. Irrigation duration is determined by crop type lookup
    """
    
    # Irrigation duration by crop type (seconds)
    DURATIONS = {
        'tomato': 600,   # 10 min
        'corn': 480,     # 8 min
        'lettuce': 300,  # 5 min
        'wheat': 240,    # 4 min
    }
    DEFAULT_DURATION = 300  # 5 min fallback
    
    def __init__(self, catalogue_url):
        self.catalogue_url = catalogue_url
        
        print("[WaterManager] Loading config...")
        config = requests.get(catalogue_url).json()
        
        self.broker = config['broker']['address']
        self.port = config['broker']['port']
        
        self.threshold = config.get('settings', {}).get('moisture_threshold', 30.0)
        
        topics = config.get('topics', {})
        self.topic_rain = topics.get('weather_alert', 'smart_irrigation/weather/alert')
        self.topic_frost = topics.get('frost_alert', 'smart_irrigation/weather/frost')
        
        self.gardens = config.get('gardens', {})
        self.sensors = {}      
        self.actuators = {}    
        
        self.rain_alert = False
        self.frost_alert = False
        
        self.client = MyMQTT('water_manager', self.broker, self.port, notifier=self)
        self.client.start()
        time.sleep(1)
        
        self._load_devices()
        self._start_auto_discovery()
        
        print(f"[WaterManager] Ready. Threshold: {self.threshold}%")

    def _load_devices(self):
        """Load devices from Catalogue."""
        try:
            devices = requests.get(f"{self.catalogue_url}devices").json()
            
            for d in devices:
                gid = d.get('garden_id', 'garden_1')
                fid = d.get('field_id', 'field_1')
                key = f"{gid}_{fid}"
                
                if d['type'] == 'sensor':
                    for topic in d['topics'].get('publish', []):
                        self.sensors[topic] = {'garden_id': gid, 'field_id': fid}
                elif d['type'] == 'actuator':
                    sub_topics = d['topics'].get('subscribe', [])
                    if sub_topics:
                        self.actuators[key] = sub_topics[0]
            
            print(f"[WaterManager] Devices: {len(self.sensors)} sensors, {len(self.actuators)} actuators")
        except Exception as e:
            print(f"[WaterManager] Error loading devices: {e}")

    def _start_auto_discovery(self):
        """Refresh devices every 60 seconds."""
        def loop():
            while True:
                time.sleep(60)
                old_count = len(self.sensors)
                self._load_devices()
                if len(self.sensors) > old_count:
                    self._subscribe_sensors()
        
        threading.Thread(target=loop, daemon=True).start()

    def _subscribe_sensors(self):
        """Subscribe to all sensor topics."""
        for topic in self.sensors:
            self.client.subscribe(topic, qos=0)

    def _get_duration(self, garden_id, field_id):
        """Get irrigation duration based on crop type."""
        try:
            crop = self.gardens[garden_id]['fields'][field_id].get('crop_type', '')
            return self.DURATIONS.get(crop, self.DEFAULT_DURATION)
        except KeyError:
            return self.DEFAULT_DURATION

    def notify(self, topic, payload):
        """Handle incoming MQTT messages."""
        data = json.loads(payload)
        
        # Rain alert
        if topic == self.topic_rain:
            if isinstance(data, dict) and data.get('status') == 'ACTIVE':
                self.rain_alert = True
                print("[WaterManager] Rain alert ACTIVE")
            else:
                self.rain_alert = False
                print("[WaterManager] Rain alert cleared")
            return
        
        # Frost alert
        if topic == self.topic_frost:
            if isinstance(data, dict) and data.get('status') == 'ACTIVE':
                self.frost_alert = True
                print("[WaterManager] Frost alert ACTIVE")
            else:
                self.frost_alert = False
                print("[WaterManager] Frost alert cleared")
            return
        
        # Sensor data (SenML format)
        if isinstance(data, list):
            info = self.sensors.get(topic, {})
            garden_id = info.get('garden_id', 'garden_1')
            field_id = info.get('field_id', 'field_1')
            
            moisture = None
            for m in data:
                if m.get('n') == 'soil_moisture':
                    moisture = m.get('v')
                    break
            
            if moisture is not None:
                print(f"[WaterManager] Moisture: {moisture}% ({garden_id}/{field_id})")
                self._check_irrigation(garden_id, field_id, moisture)

    def _check_irrigation(self, garden_id, field_id, moisture):
        """Decide whether to irrigate."""
        # Skip if moisture is OK
        if moisture >= self.threshold:
            print(f"[WaterManager] Moisture OK ({moisture}%)")
            return
        
        # Skip if weather alert active
        if self.rain_alert:
            print(f"[WaterManager] Low moisture but rain expected - skipping")
            return
        if self.frost_alert:
            print(f"[WaterManager] Low moisture but frost alert - skipping")
            return
        
        # Irrigate!
        key = f"{garden_id}_{field_id}"
        if key not in self.actuators:
            print(f"[WaterManager] No actuator for {key}")
            return
        
        duration = self._get_duration(garden_id, field_id)
        cmd = {'command': 'OPEN', 'duration': duration}
        self.client.publish(self.actuators[key], json.dumps(cmd))
        print(f"[WaterManager] 💧 IRRIGATING {key} for {duration}s")

    def run(self):
        """Subscribe to topics and run forever."""
        self._subscribe_sensors()
        self.client.subscribe(self.topic_rain, qos=1)
        self.client.subscribe(self.topic_frost, qos=1)
        
        print("[WaterManager] Running... (auto-discovery enabled)")
        
        while True:
            time.sleep(1)

    def stop(self):
        """Stop MQTT client."""
        self.client.stop()


if __name__ == '__main__':
    manager = WaterManager('http://localhost:8080/')
    try:
        manager.run()
    except KeyboardInterrupt:
        manager.stop()
        print("[WaterManager] Stopped")
