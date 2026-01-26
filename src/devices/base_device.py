"""
Base Device Classes for IoT Devices

This module provides base classes for sensors and actuators following
the standard course patterns. These classes reduce code duplication
by providing common functionality:

- BaseDevice: Bootstrap, registration (with dynamic ID), heartbeat, MQTT connection
- BaseSensor: Sensing and publishing readings
- BaseActuator: Command handling and status publishing

Usage:
    # New device - ID assigned by Catalogue
    class MySensor(BaseSensor):
        def sense(self):
            return {'temperature': 25.0}
    
    sensor = MySensor(catalogue_url, garden_id='garden_1', field_id='field_1')
    sensor.run()
"""

import sys
import os
from MyMQTT import MyMQTT
import time
import requests
import json
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

class BaseDevice:
    """
    Base class for all IoT devices.
    
    Provides common functionality:
    - Self-registration via POST (ID assigned by Catalogue)
    - Bootstrap from Catalogue after registration
    - Heartbeat mechanism
    - MQTT connection management
    """
    
    def __init__(self, catalogue_url, garden_id='garden_1', field_id='field_1', device_type='sensor'):
        """
        Initialize and register the device with the Catalogue.
        
        The Catalogue assigns a unique ID to this device.
        
        Args:
            catalogue_url: URL of the Catalogue service (e.g., 'http://localhost:8080/')
            garden_id: ID of the garden this device belongs to
            field_id: ID of the field within the garden
            device_type: 'sensor' or 'actuator'
        """
        self.catalogue_url = catalogue_url
        self.garden_id = garden_id
        self.field_id = field_id
        self.device_type = device_type
        self.client = None
        self.device_id = None
        self.topics = {}
        
        print(f"[{device_type}] Registering with Catalogue...")
        self._self_register()
        
        print(f"[{self.device_id}] Fetching config from {catalogue_url}...")
        res = requests.get(catalogue_url)
        self.config = res.json()
        
        self.broker = self.config['broker']['address']
        self.port = self.config['broker']['port']
        
        gardens = self.config.get('gardens', {})
        if garden_id in gardens:
            garden_config = gardens[garden_id]
            fields = garden_config.get('fields', {})
            self.field_config = fields.get(field_id, {})
        else:
            self.field_config = {}
        
        print(f"[{self.device_id}] Broker: {self.broker}:{self.port}")
        print(f"[{self.device_id}] Garden: {garden_id}, Field: {field_id}")

    def _self_register(self):
        """
        Register this device with the Catalogue via POST.
        Catalogue assigns a unique ID and returns topics.
        """
        payload = {
            "type": self.device_type,
            "garden_id": self.garden_id,
            "field_id": self.field_id,
            "name": f"{self.device_type.title()} {self.garden_id} {self.field_id}"
        }
        
        url = f"{self.catalogue_url}devices"
        res = requests.post(url, json=payload)
        result = res.json()
        
        self.device_id = result['id']
        self.topics = result.get('topics', {})
        self.name = payload['name']
        
        print(f"[{self.device_id}] Registered successfully!")
        print(f"[{self.device_id}] Topics: {self.topics}")

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
    
    def __init__(self, catalogue_url, garden_id='garden_1', field_id='field_1'):
        """Initialize the sensor and register with Catalogue."""
        super().__init__(catalogue_url, garden_id, field_id, device_type='sensor')
        
        # Get publish topics from registration response
        self.publish_topics = self.topics.get('publish', [])
        if isinstance(self.publish_topics, str):
            self.publish_topics = [self.publish_topics]
        
        print(f"[{self.device_id}] Publish topics: {self.publish_topics}")
        
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

            readings = self.sense()

            self.publish_reading(readings)
            
            reading_str = ', '.join([f"{k}={v}" for k, v in readings.items()])
            print(f"[{self.device_id}] {reading_str}")
            
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
    
    def __init__(self, catalogue_url, garden_id='garden_1', field_id='field_1'):
        """Initialize the actuator and register with Catalogue."""
        super().__init__(catalogue_url, garden_id, field_id, device_type='actuator')
        self.subscribe_topics = self.topics.get('subscribe', [])
        self.publish_topics = self.topics.get('publish', [])
        
        if isinstance(self.subscribe_topics, str):
            self.subscribe_topics = [self.subscribe_topics]
        if isinstance(self.publish_topics, str):
            self.publish_topics = [self.publish_topics]
        
        print(f"[{self.device_id}] Subscribe: {self.subscribe_topics}")
        print(f"[{self.device_id}] Publish: {self.publish_topics}")
        
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
        
        msg = []
        for name, value in status_data.items():
            msg.append({
                'bn': self.device_id,
                'n': name,
                't': timestamp,
                'v': value
            })
        
        for topic in self.publish_topics:
            self.client.publish(topic, json.dumps(msg))
            print(f"[{self.device_id}] Published status to {topic}")

    def run(self):
        """Subscribe to command topics and wait for commands."""

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
