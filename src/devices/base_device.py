"""
Base Device Classes for IoT Devices

This module provides base classes for sensors and actuators following
the standard course patterns. These classes reduce code duplication
by providing common functionality:

- BaseDevice: Bootstrap, registration, heartbeat, MQTT connection
- BaseSensor: Sensing and publishing readings
- BaseActuator: Command handling and status publishing

Usage:
    class MySensor(BaseSensor):
        def sense(self):
            # Return sensor readings
            return {'temperature': 25.0}
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

from MyMQTT import MyMQTT
import time
import requests
import json


class BaseDevice:
    """
    Base class for all IoT devices.
    
    Provides common functionality:
    - Bootstrap from Catalogue
    - Device registration via POST
    - Heartbeat mechanism
    - MQTT connection management
    """
    
    def __init__(self, catalogue_url, device_id):
        """
        Initialize the device.
        
        Args:
            catalogue_url: URL of the Catalogue service (e.g., 'http://localhost:8080/')
            device_id: Unique identifier for this device
        """
        self.catalogue_url = catalogue_url
        self.device_id = device_id
        self.client = None
        
        # Bootstrap: Get config from Catalogue
        print(f"[{device_id}] Fetching config from {catalogue_url}...")
        res = requests.get(catalogue_url)
        self.config = res.json()
        
        # Get broker info
        self.broker = self.config['broker']['address']
        self.port = self.config['broker']['port']
        
        # Find my device in the list
        self.device_config = self._find_device_config()
        if not self.device_config:
            raise ValueError(f"Device {device_id} not found in Catalogue!")
        
        self.name = self.device_config.get('name', device_id)
        
        print(f"[{device_id}] Broker: {self.broker}:{self.port}")

    def _find_device_config(self):
        """Find this device's configuration in the Catalogue."""
        for d in self.config.get('devices', []):
            if d['id'] == self.device_id:
                return d
        return None

    def register(self, device_type, publish_topics, subscribe_topics):
        """
        Register this device with the Catalogue via POST.
        
        Args:
            device_type: 'sensor' or 'actuator'
            publish_topics: List of topics this device publishes to
            subscribe_topics: List of topics this device subscribes to
        """
        payload = {
            "id": self.device_id,
            "name": self.name,
            "type": device_type,
            "topics": {
                "publish": publish_topics,
                "subscribe": subscribe_topics
            }
        }
        
        url = f"{self.catalogue_url}devices"
        res = requests.post(url, json=payload)
        result = res.json()
        print(f"[{self.device_id}] Registration: {result['status']}")

    def heartbeat(self):
        """Send heartbeat to Catalogue to keep registration alive."""
        url = f"{self.catalogue_url}devices"
        requests.post(url, json={"id": self.device_id})

    def start_mqtt(self, notifier=None):
        """
        Connect to MQTT broker.
        
        Args:
            notifier: Object with notify(topic, payload) method for callbacks
        """
        self.client = MyMQTT(self.device_id, self.broker, self.port, notifier=notifier)
        self.client.start()
        time.sleep(1)
        print(f"[{self.device_id}] MQTT connected")

    def stop(self):
        """Stop the device and disconnect from MQTT."""
        if self.client:
            self.client.stop()
        print(f"[{self.device_id}] Stopped")


class BaseSensor(BaseDevice):
    """
    Base class for sensor devices.
    
    Extends BaseDevice with:
    - Topic management for publishing
    - SenML message formatting
    - Main sensing loop
    
    Subclasses must implement:
    - sense(): Return a dictionary of sensor readings
    """
    
    def __init__(self, catalogue_url, device_id):
        """Initialize the sensor."""
        super().__init__(catalogue_url, device_id)
        
        # Get publish topics from device config
        self.publish_topics = self.device_config['topics'].get('publish', [])
        if isinstance(self.publish_topics, str):
            self.publish_topics = [self.publish_topics]
        
        print(f"[{device_id}] Topics: {self.publish_topics}")
        
        # Register with Catalogue
        self.register('sensor', self.publish_topics, [])
        
        # Start MQTT client (no notifier needed for sensors)
        self.start_mqtt()

    def sense(self):
        """
        Read sensor values. Override this method in subclasses.
        
        Returns:
            dict: Dictionary of sensor readings, e.g., {'temperature': 25.0}
        """
        raise NotImplementedError("Subclasses must implement sense()")

    def publish_reading(self, readings):
        """
        Publish sensor readings in SenML format.
        
        Args:
            readings: Dictionary of sensor readings
        """
        timestamp = time.time()
        
        # Build SenML message
        msg = []
        for name, value in readings.items():
            msg.append({
                'bn': self.device_id,
                'n': name,
                't': timestamp,
                'v': value
            })
        
        # Publish to all topics
        for topic in self.publish_topics:
            self.client.publish(topic, json.dumps(msg))

    def run(self, interval=10):
        """
        Main loop - read sensors and publish at regular intervals.
        
        Args:
            interval: Seconds between readings (default: 10)
        """
        print(f"[{self.device_id}] Running... publishing every {interval}s")
        
        heartbeat_count = 0
        heartbeat_interval = 6  # Send heartbeat every 6 readings
        
        while True:
            # Read sensors
            readings = self.sense()
            
            # Publish readings
            self.publish_reading(readings)
            
            # Print readings
            reading_str = ', '.join([f"{k}={v}" for k, v in readings.items()])
            print(f"[{self.device_id}] {reading_str}")
            
            # Heartbeat
            heartbeat_count += 1
            if heartbeat_count >= heartbeat_interval:
                self.heartbeat()
                heartbeat_count = 0
            
            time.sleep(interval)


class BaseActuator(BaseDevice):
    """
    Base class for actuator devices.
    
    Extends BaseDevice with:
    - Topic management for subscribing and publishing
    - Command handling via MQTT callback
    - Status publishing in SenML format
    
    Subclasses must implement:
    - execute_command(command, params): Execute the received command
    """
    
    def __init__(self, catalogue_url, device_id):
        """Initialize the actuator."""
        super().__init__(catalogue_url, device_id)
        
        # Get topics from device config
        self.subscribe_topics = self.device_config['topics'].get('subscribe', [])
        self.publish_topics = self.device_config['topics'].get('publish', [])
        
        if isinstance(self.subscribe_topics, str):
            self.subscribe_topics = [self.subscribe_topics]
        if isinstance(self.publish_topics, str):
            self.publish_topics = [self.publish_topics]
        
        print(f"[{device_id}] Subscribe: {self.subscribe_topics}")
        print(f"[{device_id}] Publish: {self.publish_topics}")
        
        # Register with Catalogue
        self.register('actuator', self.publish_topics, self.subscribe_topics)
        
        # Start MQTT client with this object as notifier
        self.start_mqtt(notifier=self)

    def notify(self, topic, payload):
        """
        MQTT callback when a message is received.
        Parses the command and calls execute_command().
        
        Args:
            topic: MQTT topic
            payload: Message payload (JSON string)
        """
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            print(f"[{self.device_id}] Invalid JSON received")
            return
        
        command = data.get('command', '').upper()
        print(f"[{self.device_id}] Received command: {command}")
        
        # Call subclass implementation
        self.execute_command(command, data)

    def execute_command(self, command, params):
        """
        Execute the received command. Override this method in subclasses.
        
        Args:
            command: Command string (e.g., 'OPEN', 'CLOSE')
            params: Full command parameters dictionary
        """
        raise NotImplementedError("Subclasses must implement execute_command()")

    def publish_status(self, status_data):
        """
        Publish actuator status in SenML format.
        
        Args:
            status_data: Dictionary of status values
        """
        timestamp = time.time()
        
        # Build SenML message
        msg = []
        for name, value in status_data.items():
            msg.append({
                'bn': self.device_id,
                'n': name,
                't': timestamp,
                'v': value
            })
        
        # Publish to all topics
        for topic in self.publish_topics:
            self.client.publish(topic, json.dumps(msg))
            print(f"[{self.device_id}] Published status to {topic}")

    def run(self):
        """Subscribe to command topics and wait for commands."""
        # Subscribe to command topics
        for topic in self.subscribe_topics:
            self.client.subscribe(topic, qos=1)
            print(f"[{self.device_id}] Subscribed to {topic}")
        
        print(f"[{self.device_id}] Running... waiting for commands")
        
        heartbeat_count = 0
        heartbeat_interval = 60  # Send heartbeat every 60 seconds
        
        while True:
            heartbeat_count += 1
            if heartbeat_count >= heartbeat_interval:
                self.heartbeat()
                heartbeat_count = 0
            
            time.sleep(1)
