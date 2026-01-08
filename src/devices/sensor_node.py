"""
Sensor Node - Soil Moisture and Temperature Sensor

This sensor extends BaseSensor to provide soil moisture
and temperature readings. It simulates sensor data for
testing purposes.

The sensor:
1. Bootstraps from Catalogue (via BaseSensor)
2. Registers itself via POST (via BaseSensor)
3. Publishes readings in SenML format
4. Sends heartbeats to stay registered
"""

import random
from base_device import BaseSensor


class SensorNode(BaseSensor):
    """
    Soil Moisture and Temperature Sensor Node.
    
    Extends BaseSensor with specific sensing logic for
    soil moisture and temperature readings.
    """
    
    def sense(self):
        """
        Read soil moisture and temperature.
        
        In a real implementation, this would read from
        actual hardware sensors. Here we simulate readings.
        
        Returns:
            dict: Sensor readings with 'soil_moisture' and 'temperature'
        """
        # Simulate sensor readings
        moisture = random.uniform(20.0, 80.0)
        temperature = random.uniform(15.0, 35.0)
        
        return {
            'soil_moisture': round(moisture, 1),
            'temperature': round(temperature, 1)
        }


if __name__ == '__main__':
    
    catalogue_url = 'http://localhost:8080/'
    device_id = 'sensor_node_field_1'
    
    sensor = SensorNode(catalogue_url, device_id)
    
    try:
        sensor.run(interval=10)
    except KeyboardInterrupt:
        sensor.stop()
