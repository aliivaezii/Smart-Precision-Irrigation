import time
import json
import requests
import random
from paho.mqtt import client as mqtt

# --- The Wrapper Class (from your MyMQTT.py) ---
class MQTTClient:
    def __init__(self, client_id, broker, port):
        self.client = mqtt.Client(client_id=client_id)
        self.broker = broker
        self.port = port

    def start(self):
        self.client.connect(self.broker, self.port)
        self.client.loop_start()

    def publish(self, topic, msg):
        self.client.publish(topic, msg)

# --- The Main Sensor Class (Hybrid: REST Bootstrap -> MQTT Loop) ---
class SmartSensor:
    def __init__(self, catalogue_url, device_id):
        self.catalogue_url = catalogue_url
        self.device_id = device_id
        
        # 1. BOOTSTRAP: Ask Catalogue for settings
        print(f"🌍 Connecting to Catalogue at {catalogue_url}...")
        config = self.get_configuration()
        
        # 2. Extract MQTT details
        self.broker = config['broker']['address']
        self.port = config['broker']['port']
        
        # Find MY topic in the list
        my_settings = next((d for d in config['devices'] if d['device_id'] == self.device_id), None)
        if not my_settings:
            raise ValueError(f"Device {device_id} not found in Catalogue!")
            
        self.topic_pub = my_settings['topics']['publish']
        print(f"✅ Configured! Broker: {self.broker}, Topic: {self.topic_pub}")

        # 3. START MQTT
        self.mqtt = MQTTClient(self.device_id, self.broker, self.port)
        self.mqtt.start()

    def get_configuration(self):
        response = requests.get(self.catalogue_url)
        return response.json()

    def run(self):
        print("🚀 Sensor running...")
        while True:
            # Simulate Moisture Data
            moisture = random.uniform(20.0, 60.0)
            payload = json.dumps({
                "device_id": self.device_id,
                "moisture": moisture,
                "timestamp": time.time()
            })
            
            self.mqtt.publish(self.topic_pub, payload)
            print(f"📡 Published: {moisture:.1f}%")
            time.sleep(5)

if __name__ == "__main__":
    # Create one sensor instance
    # Note: Ensure CatalogueService is running on port 8080 first!
    sensor = SmartSensor("http://localhost:8080/", "field_1_sensor")
    sensor.run()