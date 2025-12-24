"""
ActuatorNode.py - Solenoid Valve / Water Pump Controller

This actor represents physical actuators (valves, pumps) in the irrigation system.
It follows the standard course pattern:
1. __init__: Bootstrap configuration from Catalogue
2. Register itself with the Catalogue via POST
3. Subscribe to command topic via MQTT
4. Simulate valve/pump operation when commands are received
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

from MyMQTT import MyMQTT
import time
import requests
import json


class ActuatorNode:
    """
    Actuator Node - Controls Solenoid Valves and Water Pump
    
    Subscribes to command topic and simulates valve operation.
    Publishes status updates when state changes.
    """
    
    def __init__(self, catalogue_url, device_id):
        self.catalogue_url = catalogue_url
        self.device_id = device_id
        self.is_open = False
        self.last_command_time = None
        
        # 1. Bootstrap: Get config from Catalogue
        print(f"[Actuator {device_id}] Fetching config from {catalogue_url}...")
        res = requests.get(catalogue_url)
        data = res.json()
        
        # Get broker info
        self.broker = data['broker']['address']
        self.port = data['broker']['port']
        
        # 2. Find my device configuration in the list
        my_device = None
        for d in data['devices']:
            if d['id'] == device_id:
                my_device = d
                break
        
        if not my_device:
            raise ValueError(f"Device {device_id} not found in Catalogue!")
        
        # Get my topics
        self.subscribe_topics = my_device['topics'].get('subscribe', [])
        self.publish_topics = my_device['topics'].get('publish', [])
        
        if isinstance(self.subscribe_topics, str):
            self.subscribe_topics = [self.subscribe_topics]
        if isinstance(self.publish_topics, str):
            self.publish_topics = [self.publish_topics]
        
        self.name = my_device.get('name', device_id)
        
        print(f"[Actuator {device_id}] Configured:")
        print(f"    Broker: {self.broker}:{self.port}")
        print(f"    Subscribe: {self.subscribe_topics}")
        print(f"    Publish: {self.publish_topics}")
        
        # 3. Register with Catalogue (POST)
        self.register()
        
        # 4. Start MQTT client with callback
        self.client = MyMQTT(device_id, self.broker, self.port, notifier=self)
        self.client.start()
        time.sleep(1)

    def register(self):
        """Register this actuator with the Catalogue via POST."""
        payload = {
            "id": self.device_id,
            "name": self.name,
            "type": "actuator",
            "topics": {
                "subscribe": self.subscribe_topics,
                "publish": self.publish_topics
            }
        }
        
        try:
            url = f"{self.catalogue_url}devices"
            res = requests.post(url, json=payload, timeout=5)
            if res.ok:
                result = res.json()
                print(f"[Actuator {self.device_id}] Registration: {result['status']}")
            else:
                print(f"[Actuator {self.device_id}] Registration failed: {res.text}")
        except Exception as e:
            print(f"[Actuator {self.device_id}] Registration error: {e}")

    def notify(self, topic, payload):
        """
        Callback when MQTT message is received.
        Handles valve commands: OPEN, CLOSE
        """
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            print(f"[Actuator {self.device_id}] Invalid JSON received")
            return
        
        command = data.get('command', '').upper()
        duration = data.get('duration', 0)
        
        print(f"[Actuator {self.device_id}] Received command: {command}")
        
        if command == 'OPEN':
            self.open_valve(duration)
        elif command == 'CLOSE':
            self.close_valve()
        else:
            print(f"[Actuator {self.device_id}] Unknown command: {command}")

    def open_valve(self, duration=0):
        """Simulate opening the valve."""
        if not self.is_open:
            self.is_open = True
            self.last_command_time = time.time()
            
            print("=" * 50)
            print(f"[Actuator {self.device_id}] >>> VALVE OPENED <<<")
            if duration > 0:
                print(f"[Actuator {self.device_id}] Duration: {duration} seconds")
            print("=" * 50)
            
            # Publish status update
            self.publish_status("OPEN", duration)
        else:
            print(f"[Actuator {self.device_id}] Valve already open")

    def close_valve(self):
        """Simulate closing the valve."""
        if self.is_open:
            self.is_open = False
            
            print("=" * 50)
            print(f"[Actuator {self.device_id}] >>> VALVE CLOSED <<<")
            print("=" * 50)
            
            # Publish status update
            self.publish_status("CLOSED")
        else:
            print(f"[Actuator {self.device_id}] Valve already closed")

    def publish_status(self, status, duration=0):
        """Publish current valve status to the status topic."""
        msg = {
            'bn': self.device_id,
            'n': 'valve_status',
            't': time.time(),
            'v': {
                'status': status,
                'duration': duration
            }
        }
        
        for topic in self.publish_topics:
            self.client.publish(topic, json.dumps(msg))
            print(f"[Actuator {self.device_id}] Published status to {topic}")

    def heartbeat(self):
        """Send heartbeat to Catalogue (keeps registration alive)."""
        try:
            url = f"{self.catalogue_url}devices"
            payload = {"id": self.device_id}
            requests.post(url, json=payload, timeout=5)
        except:
            pass

    def run(self):
        """Subscribe to command topics and run forever."""
        # Subscribe to all command topics
        for topic in self.subscribe_topics:
            self.client.subscribe(topic, qos=1)
            print(f"[Actuator {self.device_id}] Subscribed to {topic}")
        
        print(f"[Actuator {self.device_id}] Running... waiting for commands")
        
        heartbeat_interval = 60  # seconds
        last_heartbeat = time.time()
        
        while True:
            # Send periodic heartbeat
            if time.time() - last_heartbeat > heartbeat_interval:
                self.heartbeat()
                last_heartbeat = time.time()
            
            time.sleep(1)

    def stop(self):
        """Stop the actuator and close valve."""
        if self.is_open:
            self.close_valve()
        self.client.stop()
        print(f"[Actuator {self.device_id}] Stopped")



if __name__ == '__main__':
    
    catalogue_url = 'http://localhost:8080/'
    device_id = 'actuator_valve_1'
    
    actuator = ActuatorNode(catalogue_url, device_id)
    try:
        actuator.run()
    except KeyboardInterrupt:
        actuator.stop()
        print("[Actuator] Stopped")
