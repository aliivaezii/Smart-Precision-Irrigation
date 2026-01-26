"""
Sensor Node - Soil Moisture and Temperature Sensor

This sensor extends BaseSensor to provide soil moisture
and temperature readings. It simulates sensor data for
testing purposes.

The sensor:
1. Self-registers with Catalogue (ID assigned dynamically)
2. Bootstraps broker info from Catalogue
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
        
        moisture = random.uniform(20.0, 80.0)
        temperature = random.uniform(15.0, 35.0)
        
        return {
            'soil_moisture': round(moisture, 1),
            'temperature': round(temperature, 1)
        }


if __name__ == '__main__':
    import sys
    
    catalogue_url = 'http://localhost:8080/'
    garden_id = 'garden_1'
    field_id = 'field_1'
    
    # Allow command line: python sensor_node.py garden_1 field_1
    if len(sys.argv) >= 3:
        garden_id = sys.argv[1]
        field_id = sys.argv[2]
    
    print(f"Starting sensor for {garden_id}/{field_id}...")
    
    sensor = SensorNode(catalogue_url, garden_id=garden_id, field_id=field_id)
    
    try:
        sensor.run(interval=10)
    except KeyboardInterrupt:
        sensor.stop()
