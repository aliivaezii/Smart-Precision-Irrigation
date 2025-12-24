import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'common'))

from MyMQTT import MyMQTT
import time
import requests
import json


class WaterManager:
    """
    Water Manager - Smart Irrigation Controller
    
    Subscribes to sensor data and weather alerts.
    Decides when and how long to irrigate based on:
    - Soil moisture level
    - Weather conditions (rain/frost alerts)
    - Crop type and field configuration
    
    All MQTT topics are dynamically loaded from Catalogue.
    """
    
    # Crop water requirements (mm per day at 100% deficit)
    CROP_WATER_NEEDS = {
        'tomato': 6.0,
        'wheat': 4.0,
        'corn': 5.5,
        'lettuce': 4.5,
        'default': 5.0
    }
    
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
        
        # Get field configurations for smart irrigation
        self.fields_config = data.get('fields', {})
        
        print(f"[WaterManager] Moisture threshold: {self.moisture_threshold}%")
        print(f"[WaterManager] Alert topics: rain={self.topic_weather_alert}, frost={self.topic_frost_alert}")
        print(f"[WaterManager] Fields configured: {list(self.fields_config.keys())}")
        
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

    def calculate_irrigation_duration(self, field_id, current_moisture):
        """
        Calculate irrigation duration based on crop type and moisture deficit.
        
        Formula:
        - moisture_deficit = threshold - current_moisture (as percentage)
        - water_needed_mm = (deficit / 100) * crop_water_need_per_day
        - water_liters = water_needed_mm * field_size_m2
        - duration_seconds = (water_liters / flow_rate_lpm) * 60
        """
        # Get field configuration
        field_config = self.fields_config.get(field_id, {})
        
        crop_type = field_config.get('crop_type', 'default')
        field_size = field_config.get('field_size_m2', 100)
        flow_rate = field_config.get('flow_rate_lpm', 10.0)
        
        # Get crop water need
        water_need_mm = self.CROP_WATER_NEEDS.get(crop_type, self.CROP_WATER_NEEDS['default'])
        
        # Calculate moisture deficit (how much below threshold)
        moisture_deficit = max(0, self.moisture_threshold - current_moisture)
        deficit_ratio = moisture_deficit / 100.0
        
        # Calculate water needed
        # Simplified: if 30% deficit, apply 30% of daily water need
        water_needed_mm = deficit_ratio * water_need_mm
        water_liters = water_needed_mm * field_size  # 1mm on 1m² = 1 liter
        
        # Calculate duration
        duration_seconds = (water_liters / flow_rate) * 60
        
        # Clamp to reasonable range (min 60s, max 30 min)
        duration_seconds = max(60, min(1800, duration_seconds))
        
        print(f"[WaterManager] Smart calculation for {field_id}:")
        print(f"    Crop: {crop_type}, Field: {field_size}m², Flow: {flow_rate}L/min")
        print(f"    Deficit: {moisture_deficit:.1f}%, Water needed: {water_liters:.1f}L")
        print(f"    Duration: {duration_seconds:.0f}s ({duration_seconds/60:.1f} min)")
        
        return int(duration_seconds)

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
                print("[WaterManager] 🌧️ Rain alert ACTIVE - irrigation suspended")
            else:
                self.rain_alert = False
                print("[WaterManager] Rain alert cleared")
            return
        
        # Handle frost alerts
        if topic == self.topic_frost_alert:
            if data.get('status') == 'ACTIVE':
                self.frost_alert = True
                temp = data.get('value', 'N/A')
                print(f"[WaterManager] ❄️ Frost alert ACTIVE ({temp}°C) - irrigation suspended")
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
        """
        Smart decision logic:
        - Irrigate if moisture < threshold AND no weather alerts
        - Calculate duration based on crop type and field configuration
        """
        needs_water = moisture < self.moisture_threshold
        weather_ok = not self.rain_alert and not self.frost_alert
        
        if needs_water and weather_ok:
            # Find field from device_id (e.g., sensor_node_field_1 -> field_1)
            parts = device_id.split('_')
            if len(parts) >= 3:
                field_id = f"{parts[-2]}_{parts[-1]}"
            else:
                field_id = "field_1"  # Default fallback
            
            # Calculate smart irrigation duration
            duration = self.calculate_irrigation_duration(field_id, moisture)
            
            print(f"[WaterManager] LOW MOISTURE ({moisture}%) - Starting smart irrigation for {field_id}")
            
            # Publish command to valve with calculated duration
            if field_id in self.actuator_topics:
                cmd = {'command': 'OPEN', 'duration': duration}
                self.client.publish(self.actuator_topics[field_id], json.dumps(cmd))
                print(f"[WaterManager] Sent OPEN command ({duration}s) to {self.actuator_topics[field_id]}")
        
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
        
        # Subscribe to weather alerts (using config topics, not hardcoded!)
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
