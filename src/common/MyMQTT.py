"""
Catalogue Service - Central Device and Service Registry

This is the core registry for the Smart Irrigation System.
All devices and services bootstrap from this Catalogue.

Features:
- Full CRUD operations for devices (GET/POST/PUT/DELETE)
- Dynamic device ID generation
- Multi-garden support with field configurations
- Service registration and discovery
- Persistent storage in JSON config file
"""

import paho.mqtt.client as mqtt


class MyMQTT:
    def __init__(self, client_id, broker, port, notifier=None):
        self.client_id = client_id
        self.broker = broker
        self.port = port
        self.notifier = notifier
        
        try:
            self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        except (AttributeError, TypeError):
            self.client = mqtt.Client(client_id=client_id)
        
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, *args):
        print(f"[MQTT] Connected to {self.broker}:{self.port}")

    def on_message(self, client, userdata, msg):
        if self.notifier:
            self.notifier.notify(msg.topic, msg.payload.decode())

    def start(self):
        self.client.connect(self.broker, self.port)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, topic, message, qos=0):
        self.client.publish(topic, message, qos)

    def subscribe(self, topic, qos=0):
        self.client.subscribe(topic, qos)
        print(f"[MQTT] Subscribed to {topic}")
