import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

from MyMQTT import MyMQTT
import time
import requests
import random
import json


class SensorNode:
    """
    Sensor Node - Soil Moisture and Temperature Sensor
    
    Publishes sensor readings via MQTT in SenML format.
    Registers itself with the Catalogue via POST.
    """
    
    def __init__(self, catalogue_url, device_id):
        self.catalogue_url = catalogue_url
        self.device_id = device_id
        
        # 1. Bootstrap: Get config from Catalogue
        print(f"[Sensor {device_id}] Fetching config from {catalogue_url}...")
        res = requests.get(catalogue_url)
        data = res.json()
        
        self.broker = data['broker']['address']
        self.port = data['broker']['port']
        
        # 2. Find my device in the list
        my_device = None
        for d in data['devices']:
            if d['id'] == device_id:
                my_device = d
                break
        
        if not my_device:
            raise ValueError(f"Device {device_id} not found in Catalogue!")
        
        self.name = my_device.get('name', device_id)
        self.topics = my_device['topics']['publish']
        if isinstance(self.topics, str):
            self.topics = [self.topics]
            
        print(f"[Sensor {device_id}] Broker: {self.broker}, Topics: {self.topics}")
        
        # 3. Register with Catalogue (POST)
        self.register()
        
        # 4. Start MQTT client
        self.client = MyMQTT(device_id, self.broker, self.port)
        self.client.start()
        time.sleep(1)

    def register(self):
        """Register this sensor with the Catalogue via POST."""
        payload = {
            "id": self.device_id,
            "name": self.name,
            "type": "sensor",
            "topics": {"publish": self.topics, "subscribe": []}
        }
        
        url = f"{self.catalogue_url}devices"
        res = requests.post(url, json=payload)
        result = res.json()
        print(f"[Sensor {self.device_id}] Registration: {result['status']}")

    def heartbeat(self):
        """Send heartbeat to Catalogue (keeps registration alive)."""
        url = f"{self.catalogue_url}devices"
        requests.post(url, json={"id": self.device_id})

    def sense(self):
        """Simulate sensor reading (like BaseSensor.sense())"""
        moisture = random.uniform(20.0, 80.0)
        temperature = random.uniform(15.0, 35.0)
        return {
            'soil_moisture': round(moisture, 1),
            'temperature': round(temperature, 1)
        }

    def run(self, freq=10):
        """Main loop - publish sensor readings in SenML format."""
        print(f"[Sensor {self.device_id}] Running... publishing every {freq}s")
        
        count = 0
        while True:
            reading = self.sense()
            
            # SenML format: list of measurements
            msg = [
                {'bn': self.device_id, 'n': 'soil_moisture', 't': time.time(), 'v': reading['soil_moisture']},
                {'bn': self.device_id, 'n': 'temperature', 't': time.time(), 'v': reading['temperature']}
            ]
            
            for topic in self.topics:
                self.client.publish(topic, json.dumps(msg))
            
            print(f"[Sensor {self.device_id}] moisture={reading['soil_moisture']}%, temp={reading['temperature']}°C")
            
            # Heartbeat every 6 readings (~60s if freq=10)
            count += 1
            if count >= 6:
                self.heartbeat()
                count = 0
            
            time.sleep(freq)

    def stop(self):
        """Stop the sensor node."""
        self.client.stop()
        print(f"[Sensor {self.device_id}] Stopped")


if __name__ == '__main__':
    
    catalogue_url = 'http://localhost:8080/'
    device_id = 'sensor_node_field_1'
    
    sensor = SensorNode(catalogue_url, device_id)
    try:
        sensor.run(freq=10)
    except KeyboardInterrupt:
        sensor.stop()
