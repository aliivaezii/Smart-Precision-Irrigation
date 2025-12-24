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
    
    # Crop factor: multiplier for water needs (higher = more water)
    # Used in formula: water_needed_mm = (target - current) * crop_factor
    CROP_FACTORS = {
        'tomato': 1.2,      # High water demand
        'lettuce': 0.8,     # Low water demand  
        'wheat': 0.6,       # Lower water demand
        'corn': 1.0,        # Medium water demand
        'default': 1.0
    }
    
    # Fallback: simple duration lookup (seconds) if config missing
    CROP_DURATION_LOOKUP = {
        'tomato': 600,      # 10 minutes
        'lettuce': 300,     # 5 minutes
        'wheat': 240,       # 4 minutes
        'corn': 480,        # 8 minutes
        'default': 300      # 5 minutes
    }
    
    # Target soil moisture percentage
    TARGET_MOISTURE = 70.0
    
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
        
        Smart Formula (as per proposal):
        - water_needed_mm = (target_moisture - current_moisture) * crop_factor
        - total_liters = water_needed_mm * field_size_m2
        - duration_sec = total_liters / (flow_rate_lpm / 60)
        
        Falls back to lookup table if field config is missing.
        """
        # Get field configuration
        field_config = self.fields_config.get(field_id, {})
        
        # If no config, use simple lookup table
        if not field_config:
            print(f"[WaterManager] No config for {field_id}, using lookup table")
            crop_type = 'default'
            return self.CROP_DURATION_LOOKUP.get(crop_type, 300)
        
        crop_type = field_config.get('crop_type', 'default')
        field_size = field_config.get('field_size_m2', 100)
        flow_rate_lpm = field_config.get('flow_rate_lpm', 20.0)
        
        # Get crop factor
        crop_factor = self.CROP_FACTORS.get(crop_type, self.CROP_FACTORS['default'])
        
        # Calculate moisture deficit (how much below target)
        moisture_deficit = max(0, self.TARGET_MOISTURE - current_moisture)
        
        # Smart Formula:
        # water_needed_mm = (target - current) * crop_factor
        water_needed_mm = moisture_deficit * crop_factor
        
        # total_liters = water_needed_mm * field_size_m2 (1mm on 1m² = 1 liter)
        total_liters = water_needed_mm * field_size
        
        # duration_sec = total_liters / flow_rate_lps
        # flow_rate_lps = flow_rate_lpm / 60
        flow_rate_lps = flow_rate_lpm / 60.0
        duration_seconds = total_liters / flow_rate_lps
        
        # Clamp to reasonable range (min 60s, max 30 min)
        duration_seconds = max(60, min(1800, duration_seconds))
        
        print(f"[WaterManager] Smart calculation for {field_id}:")
        print(f"    Crop: {crop_type} (factor={crop_factor}), Field: {field_size}m²")
        print(f"    Moisture: {current_moisture}% → Target: {self.TARGET_MOISTURE}%")
        print(f"    Water needed: {water_needed_mm:.1f}mm = {total_liters:.1f}L")
        print(f"    Flow: {flow_rate_lpm}L/min → Duration: {duration_seconds:.0f}s")
        
        return int(duration_seconds)

    def notify(self, topic, payload):
        """Callback when MQTT message received."""
        try:
            data = json.loads(payload)
        except:
            return
        
        # Handle weather alerts (rain) - dict format
        if topic == self.topic_weather_alert:
            if isinstance(data, dict) and data.get('status') == 'ACTIVE':
                self.rain_alert = True
                print("[WaterManager] 🌧️ Rain alert ACTIVE - irrigation suspended")
            else:
                self.rain_alert = False
                print("[WaterManager] Rain alert cleared")
            return
        
        # Handle frost alerts - dict format
        if topic == self.topic_frost_alert:
            if isinstance(data, dict) and data.get('status') == 'ACTIVE':
                self.frost_alert = True
                temp = data.get('value', 'N/A')
                print(f"[WaterManager] ❄️ Frost alert ACTIVE ({temp}°C) - irrigation suspended")
            else:
                self.frost_alert = False
                print("[WaterManager] Frost alert cleared")
            return
        
        # Handle sensor data in SenML format (list of measurements)
        # Format: [{'bn': '...', 'n': 'soil_moisture', 't': ..., 'v': 25}, ...]
        if isinstance(data, list):
            device_id = None
            moisture = None
            
            for measurement in data:
                if 'bn' in measurement:
                    device_id = measurement['bn']
                if measurement.get('n') == 'soil_moisture':
                    moisture = measurement['v']
            
            if device_id and moisture is not None:
                self.memory[device_id] = moisture
                print(f"[WaterManager] Received: {device_id} -> moisture={moisture}%")
                self.evaluate(device_id, moisture)
            return
        
        # Fallback: Handle old dict format (backward compatibility)
        if isinstance(data, dict) and 'v' in data:
            if isinstance(data['v'], dict) and 'soil_moisture' in data['v']:
                device_id = data.get('bn', 'unknown')
                moisture = data['v']['soil_moisture']
                self.memory[device_id] = moisture
                print(f"[WaterManager] Received: {device_id} -> moisture={moisture}%")
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
