import json
from abc import ABC, abstractmethod

class IoTDevice(ABC):
    """
    Abstract Base Class for all IoT Devices (Sensors & Actuators).
    Enforces the structure defined in the proposal.
    """
    def __init__(self, device_id, topic_pub, topic_sub):
        self.device_id = device_id
        self.topic_pub = topic_pub
        self.topic_sub = topic_sub
        self.connected = False

    @abstractmethod
    def start(self):
        """Connect to MQTT Broker and start loops."""
        pass

    @abstractmethod
    def get_status(self):
        """Return the current health or value of the device."""
        pass

    def to_json(self):
        """Helper to format data for MQTT transmission."""
        return json.dumps({
            "device_id": self.device_id,
            "status": self.get_status()
        })