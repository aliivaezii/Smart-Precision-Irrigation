import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

from MyMQTT import MyMQTT
import time
import requests
import random
import json


class SensorNode:
    
    
    def __init__(self, catalogue_url, device_id):
        self.device_id = device_id
        
        # 1. Bootstrap: Get config from Catalogue
        print(f"[Sensor] Fetching config from {catalogue_url}...")
        res = requests.get(catalogue_url)
        data = res.json()
        
        self.broker = data['broker']['address']
        self.port = data['broker']['port']
        
        # Find my device in the list
        my_device = None
        for d in data['devices']:
            if d['id'] == device_id:
                my_device = d
                break
        
        if not my_device:
            raise ValueError(f"Device {device_id} not found in Catalogue!")
        
        self.topics = my_device['topics']['publish']
        if isinstance(self.topics, str):
            self.topics = [self.topics]
            
        print(f"[Sensor] Configured: broker={self.broker}, topics={self.topics}")
        
        
        self.client = MyMQTT(device_id, self.broker, self.port)
        self.client.start()
        time.sleep(1)

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
        print(f"[Sensor] Running... publishing every {freq}s")
        while True:
            reading = self.sense()
            
            # SenML format as per course reference:
            # List of measurements, each with bn, n, t, v (single value)
            msg = [
                {
                    'bn': self.device_id,
                    'n': 'soil_moisture',
                    't': time.time(),
                    'v': reading['soil_moisture']
                },
                {
                    'bn': self.device_id,
                    'n': 'temperature',
                    't': time.time(),
                    'v': reading['temperature']
                }
            ]
            
            for topic in self.topics:
                self.client.publish(topic, json.dumps(msg))
                print(f"[Sensor] Published to {topic}: moisture={reading['soil_moisture']}%")
            
            time.sleep(freq)

    def stop(self):
        self.client.stop()


if __name__ == '__main__':
    
    catalogue_url = 'http://localhost:8080/'
    device_id = 'sensor_node_field_1'
    
    sensor = SensorNode(catalogue_url, device_id)
    try:
        sensor.run(freq=10)
    except KeyboardInterrupt:
        sensor.stop()
        print("[Sensor] Stopped")
