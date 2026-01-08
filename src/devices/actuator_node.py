"""
Actuator Node - Solenoid Valve Controller

This actuator extends BaseActuator to control solenoid valves
in a gravity-fed irrigation system.

The actuator:
1. Bootstraps from Catalogue (via BaseActuator)
2. Registers itself via POST (via BaseActuator)
3. Subscribes to command topics via MQTT
4. Executes valve OPEN/CLOSE commands
5. Tracks and publishes water consumption
"""

import time
import json
from base_device import BaseActuator


class ActuatorNode(BaseActuator):
    """
    Solenoid Valve Controller for Gravity-Fed Irrigation.
    
    Extends BaseActuator with valve control logic and
    water consumption tracking.
    """
    
    # Default flow rate (can be overridden by Catalogue config)
    DEFAULT_FLOW_RATE = 20.0  # Liters per minute
    
    def __init__(self, catalogue_url, device_id):
        """Initialize the valve actuator."""
        # Call parent init (bootstrap, register, start MQTT)
        super().__init__(catalogue_url, device_id)
        
        # Valve state
        self.is_open = False
        self.last_command_time = None
        self.current_duration = 0
        
        # Get field-specific config for flow rate
        field_id = '_'.join(device_id.split('_')[-2:])  # e.g., "field_1"
        fields_config = self.config.get('fields', {})
        field_config = fields_config.get(field_id, {})
        self.flow_rate = field_config.get('flow_rate_lpm', self.DEFAULT_FLOW_RATE)
        
        # Get resource monitoring topic
        topics_config = self.config.get('topics', {})
        self.topic_resource = topics_config.get('resource_usage', 'smart_irrigation/irrigation/usage')
        
        print(f"[{device_id}] Flow rate: {self.flow_rate} L/min")

    def execute_command(self, command, params):
        """
        Execute valve commands.
        
        Args:
            command: 'OPEN' or 'CLOSE'
            params: Command parameters (may include 'duration')
        """
        if command == 'OPEN':
            duration = params.get('duration', 0)
            self.open_valve(duration)
        elif command == 'CLOSE':
            self.close_valve()
        else:
            print(f"[{self.device_id}] Unknown command: {command}")

    def open_valve(self, duration=0):
        """Open the valve."""
        if self.is_open:
            print(f"[{self.device_id}] Valve already open")
            return
        
        self.is_open = True
        self.last_command_time = time.time()
        self.current_duration = duration
        
        print("=" * 50)
        print(f"[{self.device_id}] >>> VALVE OPENED <<<")
        if duration > 0:
            print(f"[{self.device_id}] Duration: {duration} seconds")
        print("=" * 50)
        
        # Publish status
        self.publish_status({
            'valve_status': 'OPEN',
            'duration': duration
        })

    def close_valve(self):
        """Close the valve and calculate water usage."""
        if not self.is_open:
            print(f"[{self.device_id}] Valve already closed")
            return
        
        self.is_open = False
        
        # Calculate duration and water consumption
        actual_duration = 0
        if self.last_command_time:
            actual_duration = time.time() - self.last_command_time
        
        # Water usage: flow_rate (L/min) * duration (min)
        water_liters = (self.flow_rate * actual_duration) / 60.0
        
        print("=" * 50)
        print(f"[{self.device_id}] >>> VALVE CLOSED <<<")
        print(f"[{self.device_id}] Duration: {actual_duration:.1f}s")
        print(f"[{self.device_id}] Water used: {water_liters:.2f} liters")
        print("=" * 50)
        
        # Publish status
        self.publish_status({
            'valve_status': 'CLOSED',
            'duration': actual_duration
        })
        
        # Publish resource usage for ThingSpeak
        self.publish_resource_usage(water_liters, actual_duration)

    def publish_resource_usage(self, water_liters, duration):
        """
        Publish water consumption in SenML format.
        
        Args:
            water_liters: Amount of water used
            duration: Duration in seconds
        """
        msg = [
            {
                'bn': self.device_id,
                'n': 'water_liters',
                't': time.time(),
                'v': round(water_liters, 2)
            },
            {
                'bn': self.device_id,
                'n': 'duration_sec',
                't': time.time(),
                'v': round(duration, 1)
            }
        ]
        
        self.client.publish(self.topic_resource, json.dumps(msg))
        print(f"[{self.device_id}] Published usage: {water_liters:.2f}L")

    def stop(self):
        """Stop the actuator and close valve if open."""
        if self.is_open:
            self.close_valve()
        super().stop()


if __name__ == '__main__':
    
    catalogue_url = 'http://localhost:8080/'
    device_id = 'actuator_valve_1'
    
    actuator = ActuatorNode(catalogue_url, device_id)
    
    try:
        actuator.run()
    except KeyboardInterrupt:
        actuator.stop()
        print("[Actuator] Stopped")
