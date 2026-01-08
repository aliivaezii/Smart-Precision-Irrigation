"""
Device Simulator - Auto-Discovery Mode

This script automatically discovers ALL registered devices from the Catalogue
and simulates them. No need to manually specify garden_id/field_id!

How it works:
1. Connects to the Catalogue to get the list of registered devices
2. For each sensor: publishes simulated readings every 10 seconds
3. For each actuator: listens for valve commands and responds
4. Checks for new devices every 60 seconds

Usage:
    python src/devices/device_simulator.py

This is the RECOMMENDED way to run device simulations for testing.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

from MyMQTT import MyMQTT
import time
import requests
import json
import random
import threading


# Configuration
CATALOGUE_URL = "http://localhost:8080/"
SENSOR_PUBLISH_INTERVAL = 10  # seconds between sensor readings
DEVICE_CHECK_INTERVAL = 60    # seconds between checking for new devices


class SensorSimulator:
    """
    Simulates a single sensor device.
    Publishes soil moisture and temperature readings.
    """
    
    def __init__(self, device_id, topics, broker, port):
        self.device_id = device_id
        self.topics = topics
        self.running = True
        
        # Create MQTT client
        self.client = MyMQTT(device_id, broker, port)
        self.client.start()
        time.sleep(0.5)
        
        print(f"[{device_id}] Sensor simulator started")
    
    def publish_readings(self):
        """Generate and publish simulated sensor readings."""
        # Generate random readings
        moisture = round(random.uniform(20.0, 80.0), 1)
        temperature = round(random.uniform(15.0, 35.0), 1)
        timestamp = time.time()
        
        # Publish to each topic
        for topic in self.topics:
            if 'soil_moisture' in topic:
                msg = [{'bn': self.device_id, 'n': 'soil_moisture', 't': timestamp, 'v': moisture}]
                self.client.publish(topic, json.dumps(msg))
            elif 'temperature' in topic:
                msg = [{'bn': self.device_id, 'n': 'temperature', 't': timestamp, 'v': temperature}]
                self.client.publish(topic, json.dumps(msg))
        
        print(f"[{self.device_id}] moisture={moisture}%, temp={temperature}°C")
    
    def stop(self):
        """Stop the sensor simulation."""
        self.running = False
        self.client.stop()


class ActuatorSimulator:
    """
    Simulates a single actuator device (valve).
    Listens for commands and responds.
    """
    
    def __init__(self, device_id, subscribe_topics, publish_topics, broker, port, resource_topic):
        self.device_id = device_id
        self.subscribe_topics = subscribe_topics
        self.publish_topics = publish_topics
        self.resource_topic = resource_topic
        self.running = True
        
        # Valve state
        self.valve_open = False
        self.open_time = 0
        self.flow_rate = 20.0  # Liters per minute
        
        # Create MQTT client with self as notifier (to receive messages)
        self.client = MyMQTT(device_id, broker, port, notifier=self)
        self.client.start()
        time.sleep(0.5)
        
        # Subscribe to command topics
        for topic in subscribe_topics:
            self.client.subscribe(topic, qos=1)
            print(f"[{device_id}] Subscribed to: {topic}")
        
        print(f"[{device_id}] Actuator simulator started")
    
    def notify(self, topic, payload):
        """Called when MQTT message is received."""
        try:
            data = json.loads(payload)
            command = data.get('command', '')
            duration = data.get('duration', 0)
            
            if command == 'OPEN':
                self.open_valve(duration)
            elif command == 'CLOSE':
                self.close_valve()
        except Exception as e:
            print(f"[{self.device_id}] Error: {e}")
    
    def open_valve(self, duration):
        """Open the valve."""
        if self.valve_open:
            print(f"[{self.device_id}] Valve already open")
            return
        
        self.valve_open = True
        self.open_time = time.time()
        
        print("=" * 50)
        print(f"[{self.device_id}] >>> VALVE OPENED <<<")
        print(f"[{self.device_id}] Duration: {duration} seconds")
        print("=" * 50)
        
        # Publish status
        self.publish_status('OPEN')
        
        # Schedule auto-close after duration
        if duration > 0:
            timer = threading.Timer(duration, self.close_valve)
            timer.start()
    
    def close_valve(self):
        """Close the valve and report water usage."""
        if not self.valve_open:
            return
        
        self.valve_open = False
        
        # Calculate water used
        actual_duration = time.time() - self.open_time
        water_liters = (self.flow_rate * actual_duration) / 60.0
        
        print("=" * 50)
        print(f"[{self.device_id}] >>> VALVE CLOSED <<<")
        print(f"[{self.device_id}] Duration: {actual_duration:.1f}s, Water: {water_liters:.2f}L")
        print("=" * 50)
        
        # Publish status
        self.publish_status('CLOSED')
        
        # Publish resource usage
        self.publish_resource_usage(water_liters, actual_duration)
    
    def publish_status(self, status):
        """Publish valve status."""
        for topic in self.publish_topics:
            if 'valve_status' in topic:
                msg = [{'bn': self.device_id, 'n': 'valve_status', 't': time.time(), 'vs': status}]
                self.client.publish(topic, json.dumps(msg))
    
    def publish_resource_usage(self, water_liters, duration):
        """Publish water usage."""
        msg = [
            {'bn': self.device_id, 'n': 'water_liters', 't': time.time(), 'v': round(water_liters, 2)},
            {'bn': self.device_id, 'n': 'duration_sec', 't': time.time(), 'v': round(duration, 1)}
        ]
        self.client.publish(self.resource_topic, json.dumps(msg))
        print(f"[{self.device_id}] Published: {water_liters:.2f}L used")
    
    def stop(self):
        """Stop the actuator simulation."""
        self.running = False
        if self.valve_open:
            self.close_valve()
        self.client.stop()


def get_config():
    """Fetch configuration from Catalogue."""
    print(f"Connecting to Catalogue at {CATALOGUE_URL}...")
    response = requests.get(CATALOGUE_URL)
    return response.json()


def get_devices():
    """Fetch list of registered devices from Catalogue."""
    response = requests.get(CATALOGUE_URL + "devices")
    return response.json()


def register_default_devices():
    """Register default devices if none exist."""
    devices = get_devices()
    
    if len(devices) > 0:
        print(f"Found {len(devices)} existing device(s), skipping auto-registration.")
        return
    
    print("No devices found. Registering default devices...")
    
    # Default devices to register
    default_devices = [
        {"type": "sensor", "garden_id": "garden_1", "field_id": "field_1", "name": "Sensor Garden 1 Field 1"},
        {"type": "actuator", "garden_id": "garden_1", "field_id": "field_1", "name": "Valve Garden 1 Field 1"},
    ]
    
    for device in default_devices:
        try:
            response = requests.post(CATALOGUE_URL + "devices", json=device)
            result = response.json()
            print(f"  Registered: {result.get('id', 'unknown')}")
        except Exception as e:
            print(f"  Failed to register {device['type']}: {e}")
    
    print()


def main():
    """Main function - discovers and simulates all devices."""
    
    print()
    print("=" * 60)
    print("Device Simulator - Auto-Discovery Mode")
    print("=" * 60)
    print()
    print("  This simulator automatically discovers and simulates")
    print("  all devices registered in the Catalogue.")
    print()
    print("  To add a new device, use Postman:")
    print("    POST http://localhost:8080/devices")
    print('    {"type": "sensor", "garden_id": "garden_1", "field_id": "field_2"}')
    print()
    print("  The simulator will detect it within 60 seconds!")
    print()
    print("=" * 60)
    print()
    
    # Get configuration from Catalogue
    config = get_config()
    broker = config['broker']['address']
    port = config['broker']['port']
    resource_topic = config.get('topics', {}).get('resource_usage', 'smart_irrigation/irrigation/usage')
    
    print(f"Broker: {broker}:{port}")
    print()
    
    # Register default devices if none exist
    register_default_devices()
    
    # Keep track of active simulators
    sensors = {}      # device_id -> SensorSimulator
    actuators = {}    # device_id -> ActuatorSimulator
    
    # Main loop
    running = True
    last_check = 0
    
    try:
        while running:
            current_time = time.time()
            
            # Check for new devices every DEVICE_CHECK_INTERVAL seconds
            if current_time - last_check >= DEVICE_CHECK_INTERVAL:
                last_check = current_time
                print(f"\n[Simulator] Checking for devices...")
                
                devices = get_devices()
                
                for device in devices:
                    device_id = device['id']
                    device_type = device.get('type', '')
                    topics = device.get('topics', {})
                    
                    # Start sensor simulator if not already running
                    if device_type == 'sensor' and device_id not in sensors:
                        publish_topics = topics.get('publish', [])
                        sensors[device_id] = SensorSimulator(device_id, publish_topics, broker, port)
                    
                    # Start actuator simulator if not already running
                    elif device_type == 'actuator' and device_id not in actuators:
                        subscribe_topics = topics.get('subscribe', [])
                        publish_topics = topics.get('publish', [])
                        actuators[device_id] = ActuatorSimulator(
                            device_id, subscribe_topics, publish_topics, broker, port, resource_topic
                        )
                
                print(f"[Simulator] Active: {len(sensors)} sensors, {len(actuators)} actuators")
            
            # Publish sensor readings
            for sensor in sensors.values():
                if sensor.running:
                    sensor.publish_readings()
            
            # Wait before next cycle
            time.sleep(SENSOR_PUBLISH_INTERVAL)
    
    except KeyboardInterrupt:
        print("\n[Simulator] Shutting down...")
    
    # Stop all simulators
    for sensor in sensors.values():
        sensor.stop()
    for actuator in actuators.values():
        actuator.stop()
    
    print("[Simulator] All simulations stopped.")


# Run the simulator
if __name__ == '__main__':
    main()
