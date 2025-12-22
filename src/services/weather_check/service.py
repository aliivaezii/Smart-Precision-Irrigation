import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'common'))

from MyMQTT import MyMQTT
import time
import requests
import json
import threading


class WeatherCheck:
    """Weather service with background thread polling."""
    
    API_URL = "https://api.open-meteo.com/v1/forecast"
    
    def __init__(self, catalogue_url):
        # 1. Bootstrap: Get config from Catalogue
        print(f"[Weather] Fetching config from {catalogue_url}...")
        res = requests.get(catalogue_url)
        data = res.json()
        
        self.broker = data['broker']['address']
        self.port = data['broker']['port']
        
        # Get location settings
        settings = data.get('settings', {})
        self.lat = settings.get('lat', 45.06)
        self.lon = settings.get('lon', 7.66)
        self.threshold = settings.get('rain_threshold_mm', 5.0)
        
        print(f"[Weather] Location: ({self.lat}, {self.lon}), threshold: {self.threshold}mm")
        
        # 2. Start MQTT
        self.client = MyMQTT('weather_service', self.broker, self.port)
        self.client.start()
        time.sleep(1)
        
        self.rain_alert_active = False
        self.running = False

    def check_weather(self):
        """Fetch weather from Open-Meteo API."""
        params = {
            'latitude': self.lat,
            'longitude': self.lon,
            'hourly': 'precipitation',
            'forecast_days': 1
        }
        
        try:
            res = requests.get(self.API_URL, params=params, timeout=10)
            data = res.json()
            
            precipitation = data.get('hourly', {}).get('precipitation', [])
            total = sum(p for p in precipitation if p)
            
            print(f"[Weather] Forecast: {total}mm precipitation in next 24h")
            return total
            
        except Exception as e:
            print(f"[Weather] API error: {e}")
            return 0

    def publish_alert(self, rain_mm):
        """Publish rain alert if threshold exceeded."""
        if rain_mm >= self.threshold and not self.rain_alert_active:
            # Send RAIN_ALERT
            msg = {
                'alert_type': 'RAIN_ALERT',
                'status': 'ACTIVE',
                'precipitation_mm': rain_mm,
                't': time.time()
            }
            self.client.publish('weather/alert', json.dumps(msg), qos=1)
            self.rain_alert_active = True
            print(f"[Weather] RAIN ALERT sent! ({rain_mm}mm expected)")
            
        elif rain_mm < self.threshold and self.rain_alert_active:
            # Clear alert
            msg = {
                'alert_type': 'RAIN_ALERT',
                'status': 'CLEARED',
                'precipitation_mm': rain_mm,
                't': time.time()
            }
            self.client.publish('weather/alert', json.dumps(msg), qos=1)
            self.rain_alert_active = False
            print(f"[Weather] Rain alert cleared")

    def _poll_loop(self, interval):
        """Background thread that polls weather."""
        while self.running:
            rain = self.check_weather()
            self.publish_alert(rain)
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
