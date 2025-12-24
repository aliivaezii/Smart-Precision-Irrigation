import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'common'))

from MyMQTT import MyMQTT
import time
import requests
import json
import threading


class WeatherCheck:
    """
    Weather Check Service - Climate Anomaly Detection
    
    Monitors weather forecasts and publishes alerts for:
    - Rain (precipitation > threshold)
    - Frost (temperature < threshold)
    
    All MQTT topics are dynamically loaded from Catalogue.
    """
    
    API_URL = "https://api.open-meteo.com/v1/forecast"
    
    def __init__(self, catalogue_url):
        # 1. Bootstrap: Get config from Catalogue
        print(f"[Weather] Fetching config from {catalogue_url}...")
        res = requests.get(catalogue_url)
        data = res.json()
        
        # Get broker info
        self.broker = data['broker']['address']
        self.port = data['broker']['port']
        
        # Get location settings
        settings = data.get('settings', {})
        self.lat = settings.get('lat', 45.06)
        self.lon = settings.get('lon', 7.66)
        self.rain_threshold = settings.get('rain_threshold_mm', 5.0)
        self.frost_threshold = settings.get('frost_threshold_c', 2.0)
        
        # Get MQTT topics from config (NO HARDCODING!)
        topics = data.get('topics', {})
        self.topic_weather_alert = topics.get('weather_alert', 'weather/alert')
        self.topic_frost_alert = topics.get('frost_alert', 'weather/frost')
        
        print(f"[Weather] Location: ({self.lat}, {self.lon})")
        print(f"[Weather] Rain threshold: {self.rain_threshold}mm")
        print(f"[Weather] Frost threshold: {self.frost_threshold}°C")
        print(f"[Weather] Topics: rain={self.topic_weather_alert}, frost={self.topic_frost_alert}")
        
        # 2. Start MQTT
        self.client = MyMQTT('weather_service', self.broker, self.port)
        self.client.start()
        time.sleep(1)
        
        # Alert state flags
        self.rain_alert_active = False
        self.frost_alert_active = False
        self.running = False

    def check_weather(self):
        """
        Fetch weather from Open-Meteo API.
        Returns tuple: (total_precipitation_mm, min_temperature_c)
        """
        params = {
            'latitude': self.lat,
            'longitude': self.lon,
            'hourly': 'precipitation,temperature_2m',
            'forecast_days': 1
        }
        
        try:
            res = requests.get(self.API_URL, params=params, timeout=10)
            data = res.json()
            
            # Get precipitation data
            precipitation = data.get('hourly', {}).get('precipitation', [])
            total_rain = sum(p for p in precipitation if p)
            
            # Get temperature data
            temperatures = data.get('hourly', {}).get('temperature_2m', [])
            min_temp = min(temperatures) if temperatures else 10.0
            
            print(f"[Weather] Forecast: {total_rain:.1f}mm rain, min temp: {min_temp:.1f}°C")
            return total_rain, min_temp
            
        except Exception as e:
            print(f"[Weather] API error: {e}")
            return 0, 10.0  # Safe defaults

    def publish_rain_alert(self, rain_mm):
        """Publish rain alert if threshold exceeded."""
        if rain_mm >= self.rain_threshold and not self.rain_alert_active:
            # Send RAIN_ALERT - ACTIVE
            msg = {
                'alert_type': 'RAIN_ALERT',
                'status': 'ACTIVE',
                'precipitation_mm': rain_mm,
                'msg': f'Warning: Heavy rain expected ({rain_mm:.1f}mm)',
                't': time.time()
            }
            self.client.publish(self.topic_weather_alert, json.dumps(msg), qos=1)
            self.rain_alert_active = True
            print(f"[Weather] RAIN ALERT sent! ({rain_mm:.1f}mm expected)")
            
        elif rain_mm < self.rain_threshold and self.rain_alert_active:
            # Send RAIN_ALERT - CLEARED
            msg = {
                'alert_type': 'RAIN_ALERT',
                'status': 'CLEARED',
                'precipitation_mm': rain_mm,
                'msg': 'Rain alert cleared',
                't': time.time()
            }
            self.client.publish(self.topic_weather_alert, json.dumps(msg), qos=1)
            self.rain_alert_active = False
            print(f"[Weather] Rain alert cleared")

    def publish_frost_alert(self, min_temp):
        """Publish frost alert if temperature below threshold."""
        if min_temp <= self.frost_threshold and not self.frost_alert_active:
            # Send FROST_ALERT - ACTIVE
            msg = {
                'alert_type': 'FROST_ALERT',
                'status': 'ACTIVE',
                'value': min_temp,
                'msg': f'Warning: Frost detected! Min temp: {min_temp:.1f}°C',
                't': time.time()
            }
            self.client.publish(self.topic_frost_alert, json.dumps(msg), qos=1)
            self.frost_alert_active = True
            print(f"[Weather] ❄️ FROST ALERT sent! (min temp: {min_temp:.1f}°C)")
            
        elif min_temp > self.frost_threshold and self.frost_alert_active:
            # Send FROST_ALERT - CLEARED
            msg = {
                'alert_type': 'FROST_ALERT',
                'status': 'CLEARED',
                'value': min_temp,
                'msg': 'Frost alert cleared',
                't': time.time()
            }
            self.client.publish(self.topic_frost_alert, json.dumps(msg), qos=1)
            self.frost_alert_active = False
            print(f"[Weather] Frost alert cleared")

    def _poll_loop(self, interval):
        """Background thread that polls weather."""
        while self.running:
            # Get weather data
            rain_mm, min_temp = self.check_weather()
            
            # Check and publish alerts
            self.publish_rain_alert(rain_mm)
            self.publish_frost_alert(min_temp)
            
            time.sleep(interval)

    def run(self, interval=3600):
        """Start background polling thread."""
        self.running = True
        
        # Start polling thread
        thread = threading.Thread(target=self._poll_loop, args=(interval,))
        thread.daemon = True
        thread.start()
        
        print(f"[Weather] Running... checking every {interval}s")
        
        # Keep main thread alive
        while self.running:
            time.sleep(1)

    def stop(self):
        self.running = False
        self.client.stop()


if __name__ == '__main__':
    catalogue_url = 'http://localhost:8080/'
    
    weather = WeatherCheck(catalogue_url)
    try:
        weather.run(interval=60)  # Check every 60s for testing
    except KeyboardInterrupt:
        weather.stop()
        print("[Weather] Stopped")
