"""
Status Service - Centralized Device Status Cache

This service:
1. Subscribes to all device topics from the Catalogue
2. Stores the latest received message for each device
3. Exposes the data via a REST API (GET)
4. Periodically updates subscriptions if new devices are added

Other services (like Telegram Bot) can query this service via REST
instead of subscribing to all topics themselves.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'common'))

from MyMQTT import MyMQTT
import json
import time
import requests
import threading
import cherrypy


class StatusService:
    """
    Status Service - REST API for device status.
    
    Subscribes to all device topics and caches the latest data.
    Exposes GET / to retrieve all cached statuses.
    """
    exposed = True

    def __init__(self, catalogue_url):
        self.catalogue_url = catalogue_url
        self.latest_data = {}  # Store: { 'device_id': { 'topic': ..., 'timestamp': ..., 'payload': ... } }
        self.subscribed_topics = set()
        self.running = True

        # 1. Bootstrap: Get Broker and Initial Config
        print(f"[StatusService] Fetching config from {self.catalogue_url}...")
        res = requests.get(self.catalogue_url)
        data = res.json()
        
        self.broker = data['broker']['address']
        self.port = data['broker']['port']
        self.base_topics = data.get('topics', {})
        
        print(f"[StatusService] Broker: {self.broker}:{self.port}")

        # 2. Start MQTT Client
        self.client = MyMQTT('status_service', self.broker, self.port, notifier=self)
        self.client.start()
        time.sleep(1)

        # 3. Initial Subscription
        self.update_subscriptions()

        # 4. Start Background Thread for Catalogue Updates
        self.updater_thread = threading.Thread(target=self.periodic_update)
        self.updater_thread.daemon = True
        self.updater_thread.start()

    def periodic_update(self):
        """Check Catalogue every 60 seconds for new devices."""
        while self.running:
            time.sleep(60)
            print("[StatusService] Checking for new devices...")
            self.update_subscriptions()

    def update_subscriptions(self):
        """Fetch all devices from Catalogue and subscribe to their publish topics."""
        # Build URL for devices endpoint
        url = self.catalogue_url
        if not url.endswith('/'):
            url += '/'
        url += 'devices'
        
        res = requests.get(url)
        devices = res.json()
        
        new_topics = []

        # Subscribe to device publish topics
        for dev in devices:
            topics = dev.get('topics', {})
            pub_topics = topics.get('publish', [])
            
            if isinstance(pub_topics, str):
                pub_topics = [pub_topics]
            
            for t in pub_topics:
                if t not in self.subscribed_topics:
                    new_topics.append(t)
                    self.subscribed_topics.add(t)

        # Subscribe to system alert topics
        for key, topic in self.base_topics.items():
            if 'alert' in key or 'status' in key:
                if topic not in self.subscribed_topics:
                    new_topics.append(topic)
                    self.subscribed_topics.add(topic)

        # Perform subscriptions
        if new_topics:
            for t in new_topics:
                self.client.subscribe(t, qos=0)
            print(f"[StatusService] Subscribed to {len(new_topics)} new topics")

    def notify(self, topic, payload):
        """MQTT Callback: Store the latest message for each device."""
        data = json.loads(payload)
        timestamp = time.time()
        
        # Extract device ID from the message
        device_id = self.extract_device_id(data, topic)

        # Get existing data for this device (if any)
        existing = self.latest_data.get(device_id, {})
        existing_payload = existing.get('payload', [])
        
        # Merge payloads - keep all measurements from same device
        if isinstance(data, list) and isinstance(existing_payload, list):
            # Create a dict of measurements by name
            measurements = {}
            for item in existing_payload:
                if isinstance(item, dict) and 'n' in item:
                    measurements[item['n']] = item
            # Update with new measurements
            for item in data:
                if isinstance(item, dict) and 'n' in item:
                    measurements[item['n']] = item
            # Convert back to list
            merged_payload = list(measurements.values())
        else:
            merged_payload = data

        # Store the merged data
        self.latest_data[device_id] = {
            "topic": topic,
            "timestamp": timestamp,
            "received_at": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp)),
            "payload": merged_payload
        }

    def extract_device_id(self, data, topic):
        """Extract device ID from message payload or topic."""
        # Try to find device ID from SenML format (list with 'bn')
        if isinstance(data, list):
            for item in data:
                if 'bn' in item:
                    return item['bn']
        
        # Try to find device ID from dict format
        if isinstance(data, dict):
            if 'bn' in data:
                return data['bn']
            if 'alert_type' in data:
                return "system_alert"

        # Extract from topic as fallback
        # Topic format: smart_irrigation/farm/field_1/...
        parts = topic.split('/')
        if len(parts) >= 3:
            return f"topic_{parts[-1]}"
        
        return "unknown"

    # ================= REST API =================
    
    @cherrypy.tools.json_out()
    def GET(self, *uri, **params):
        """
        GET /
        Returns the dictionary of all latest device statuses.
        """
        return self.latest_data

    def stop(self):
        """Stop the service."""
        self.running = False
        self.client.stop()
        print("[StatusService] Stopped")


if __name__ == '__main__':
    # Configuration
    catalogue_url = 'http://localhost:8080/'
    
    # CherryPy Configuration
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
        }
    }
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 9090
    })

    # Start Service
    service = StatusService(catalogue_url)
    cherrypy.tree.mount(service, '/', conf)
    
    print("[StatusService] Running on port 9090...")
    
    try:
        cherrypy.engine.start()
        cherrypy.engine.block()
    except KeyboardInterrupt:
        service.stop()
        cherrypy.engine.stop()
        print("[StatusService] Shutdown complete")
