import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'common'))

from MyMQTT import MyMQTT
import time
import requests
import json
import threading


class WaterManager:
    """
    Water Manager - Smart Irrigation Controller
    
    Subscribes to sensor data and weather alerts.
    Decides when and how long to irrigate based on:
    - Soil moisture level
    - Weather conditions (rain/frost alerts)
    - Crop type and field configuration
    
    All MQTT topics are dynamically loaded from Catalogue.
    Auto-discovers new devices periodically.
    """
    
    # Crop factor: multiplier for water needs (higher = more water)
    CROP_FACTORS = {
        'tomato': 1.2,
        'lettuce': 0.8,
        'wheat': 0.6,
        'corn': 1.0,
        'default': 1.0
    }
    
    # Fallback: simple duration lookup (seconds)
    CROP_DURATION_LOOKUP = {
        'tomato': 600,
        'lettuce': 300,
        'wheat': 240,
        'corn': 480,
        'default': 300
    }
    
    # Target soil moisture percentage
    TARGET_MOISTURE = 70.0
    
    # Device refresh interval (seconds)
    REFRESH_INTERVAL = 60
    
    def __init__(self, catalogue_url):
        self.catalogue_url = catalogue_url
        
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
        
        # Get MQTT topics from config
        topics = data.get('topics', {})
        self.topic_weather_alert = topics.get('weather_alert', 'smart_irrigation/weather/alert')
        self.topic_frost_alert = topics.get('frost_alert', 'smart_irrigation/weather/frost')
        
        # Get field configurations from gardens
        self.gardens_config = data.get('gardens', {})
        self.fields_config = self._build_fields_config()
        
        print(f"[WaterManager] Moisture threshold: {self.moisture_threshold}%")
        print(f"[WaterManager] Gardens configured: {list(self.gardens_config.keys())}")
        
        # Device tracking - will be refreshed periodically
        self.sensor_topics = {}
        self.actuator_topics = {}
        self._refresh_devices()
        
        # 2. Start MQTT with callback
        self.client = MyMQTT('water_manager', self.broker, self.port, notifier=self)
        self.client.start()
        time.sleep(1)
        
        # Memory for latest values
        self.memory = {}
        self.rain_alert = False
        self.frost_alert = False
        
        # Start device refresh thread
        self._start_refresh_thread()

    def _build_fields_config(self):
        """Build flat fields config from gardens structure."""
        fields = {}
        for garden_id, garden in self.gardens_config.items():
            for field_id, field_config in garden.get('fields', {}).items():
                # Key: garden_id/field_id
                key = f"{garden_id}_{field_id}"
                fields[key] = field_config
                # Also add legacy format
                fields[field_id] = field_config
        return fields

    def _refresh_devices(self):
        """Refresh device list from Catalogue (auto-discovery)."""
        try:
            res = requests.get(f"{self.catalogue_url}devices")
            devices = res.json()
            
            old_sensor_count = len(self.sensor_topics)
            old_actuator_count = len(self.actuator_topics)
            
            self.sensor_topics = {}
            self.actuator_topics = {}
            
            for d in devices:
                device_id = d['id']
                garden_id = d.get('garden_id', 'garden_1')
                field_id = d.get('field_id', 'field_1')
                
                if d['type'] == 'sensor':
                    for topic in d['topics'].get('publish', []):
                        self.sensor_topics[topic] = {
                            'device_id': device_id,
                            'garden_id': garden_id,
                            'field_id': field_id
                        }
                elif d['type'] == 'actuator':
                    # Map garden/field to valve command topic
                    key = f"{garden_id}_{field_id}"
                    subscribe_topics = d['topics'].get('subscribe', [])
                    if subscribe_topics:
                        self.actuator_topics[key] = subscribe_topics[0]
            
            new_sensors = len(self.sensor_topics) - old_sensor_count
            new_actuators = len(self.actuator_topics) - old_actuator_count
            
            if new_sensors > 0 or new_actuators > 0:
                print(f"[WaterManager] Device refresh: +{new_sensors} sensors, +{new_actuators} actuators")
                # Subscribe to new sensor topics
                self._subscribe_to_sensors()
            
            print(f"[WaterManager] Total: {len(self.sensor_topics)} sensors, {len(self.actuator_topics)} actuators")
            
        except Exception as e:
            print(f"[WaterManager] Error refreshing devices: {e}")

    def _subscribe_to_sensors(self):
        """Subscribe to all sensor topics."""
        for topic in self.sensor_topics.keys():
            self.client.subscribe(topic, qos=0)
            print(f"[WaterManager] Subscribed to {topic}")

    def _start_refresh_thread(self):
        """Start background thread to refresh devices periodically."""
        def refresh_loop():
            while True:
                time.sleep(self.REFRESH_INTERVAL)
                self._refresh_devices()
        
        thread = threading.Thread(target=refresh_loop, daemon=True)
        thread.start()
        print(f"[WaterManager] Auto-discovery enabled (every {self.REFRESH_INTERVAL}s)")

    def calculate_irrigation_duration(self, garden_id, field_id, current_moisture):
        """
        Calculate irrigation duration based on crop type and moisture deficit.
        
        Smart Formula:
        - water_needed_mm = (target_moisture - current_moisture) * crop_factor
        - total_liters = water_needed_mm * field_size_m2
        - duration_sec = total_liters / (flow_rate_lpm / 60)
        """
        # Get field configuration from garden
        field_key = f"{garden_id}_{field_id}"
        field_config = self.fields_config.get(field_key, self.fields_config.get(field_id, {}))
        
        # If no config, use simple lookup table
        if not field_config:
            print(f"[WaterManager] No config for {field_key}, using default")
            return self.CROP_DURATION_LOOKUP['default']
        
        crop_type = field_config.get('crop_type', 'default')
        field_size = field_config.get('field_size_m2', 100)
        flow_rate_lpm = field_config.get('flow_rate_lpm', 20.0)
        
        # Get crop factor
        crop_factor = self.CROP_FACTORS.get(crop_type, self.CROP_FACTORS['default'])
        
        # Calculate moisture deficit
        moisture_deficit = max(0, self.TARGET_MOISTURE - current_moisture)
        
        # Smart Formula
        water_needed_mm = moisture_deficit * crop_factor
        total_liters = water_needed_mm * field_size
        flow_rate_lps = flow_rate_lpm / 60.0
        duration_seconds = total_liters / flow_rate_lps
        
        # Clamp to reasonable range (min 60s, max 30 min)
        duration_seconds = max(60, min(1800, duration_seconds))
        
        print(f"[WaterManager] Smart calculation for {garden_id}/{field_id}:")
        print(f"    Crop: {crop_type} (factor={crop_factor}), Field: {field_size}m²")
        print(f"    Moisture: {current_moisture}% → Target: {self.TARGET_MOISTURE}%")
        print(f"    Water needed: {water_needed_mm:.1f}mm = {total_liters:.1f}L")
        print(f"    Duration: {duration_seconds:.0f}s")
        
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
                print(f"[WaterManager] ❄️ Frost alert ACTIVE ({temp}°C)")
            else:
                self.frost_alert = False
                print("[WaterManager] Frost alert cleared")
            return
        
        # Handle sensor data in SenML format
        if isinstance(data, list):
            device_id = None
            moisture = None
            garden_id = None
            field_id = None
            
            # Get garden/field info from sensor_topics mapping
            sensor_info = self.sensor_topics.get(topic, {})
            if sensor_info:
                garden_id = sensor_info.get('garden_id', 'garden_1')
                field_id = sensor_info.get('field_id', 'field_1')
            
            for measurement in data:
                if 'bn' in measurement:
                    device_id = measurement['bn']
                if measurement.get('n') == 'soil_moisture':
                    moisture = measurement['v']
            
            if device_id and moisture is not None:
                self.memory[device_id] = moisture
                print(f"[WaterManager] Received: {device_id} -> moisture={moisture}%")
                self.evaluate(device_id, moisture, garden_id, field_id)
            return

    def evaluate(self, device_id, moisture, garden_id, field_id):
        """
        Smart decision logic:
        - Irrigate if moisture < threshold AND no weather alerts
        - Calculate duration based on crop type and field configuration
        """
        needs_water = moisture < self.moisture_threshold
        weather_ok = not self.rain_alert and not self.frost_alert
        
        if needs_water and weather_ok:
            # Calculate smart irrigation duration
            duration = self.calculate_irrigation_duration(garden_id, field_id, moisture)
            
            print(f"[WaterManager] LOW MOISTURE ({moisture}%) - Starting irrigation for {garden_id}/{field_id}")
            
            # Find actuator for this garden/field
            actuator_key = f"{garden_id}_{field_id}"
            if actuator_key in self.actuator_topics:
                cmd = {'command': 'OPEN', 'duration': duration}
                self.client.publish(self.actuator_topics[actuator_key], json.dumps(cmd))
                print(f"[WaterManager] Sent OPEN ({duration}s) to {actuator_key}")
            else:
                print(f"[WaterManager] No actuator found for {actuator_key}")
        
        elif needs_water and self.rain_alert:
            print(f"[WaterManager] Low moisture but rain expected - SKIPPING")
        
        elif needs_water and self.frost_alert:
            print(f"[WaterManager] Low moisture but frost detected - SKIPPING")
        
        else:
            print(f"[WaterManager] Moisture OK ({moisture}%)")

    def run(self):
        """Subscribe to topics and run forever."""
        # Subscribe to all current sensor topics
        self._subscribe_to_sensors()
        
        # Subscribe to weather alerts
        self.client.subscribe(self.topic_weather_alert, qos=1)
        self.client.subscribe(self.topic_frost_alert, qos=1)
        
        print("[WaterManager] Running... waiting for sensor data")
        print("[WaterManager] New devices will be auto-discovered")
        
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
