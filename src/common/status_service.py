import sys
import os
import json
import time
import requests
import threading
import cherrypy

# Add common directory to path to import MyMQTT
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'common'))
from MyMQTT import MyMQTT

class StatusService:
    """
    Latest Status Service
    
    1. Subscribes to all device topics from the Catalogue.
    2. Stores the latest received message for each device.
    3. Exposes the data via a REST API (GET).
    4. Periodically updates subscriptions if new devices are added.
    """
    exposed = True

    def __init__(self, catalogue_url):
        self.catalogue_url = catalogue_url
        self.latest_data = {}  # Store: { 'device_id': { 'data': ..., 'timestamp': ... } }
        self.subscribed_topics = set()
        self.running = True

        # 1. Bootstrap: Get Broker and Initial Config
        print(f"[StatusService] Fetching config from {self.catalogue_url}...")
        try:
            res = requests.get(self.catalogue_url)
            res.raise_for_status()
            data = res.json()
            
            self.broker = data['broker']['address']
            self.port = data['broker']['port']
            self.base_topics = data.get('topics', {}) # System topics (alerts, etc.)
            
        except Exception as e:
            print(f"CRITICAL: Could not connect to Catalogue: {e}")
            sys.exit(1)

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
        """Check Catalogue every 60s for new devices."""
        while self.running:
            time.sleep(60)
            print("[StatusService] Checking for new devices...")
            self.update_subscriptions()

    def update_subscriptions(self):
        """Fetch all devices and subscribe to their publish topics."""
        try:
            # Fetch devices list
            url = f"{self.catalogue_url}devices" if self.catalogue_url.endswith('/') else f"{self.catalogue_url}/devices"
            res = requests.get(url)
            devices = res.json()
            
            new_topics = []

            # 1. Subscribe to Device Topics
            for dev in devices:
                topics = dev.get('topics', {})
                # We only care about what devices PUBLISH (sensors readings, actuator status)
                pub_topics = topics.get('publish', [])
                
                if isinstance(pub_topics, str): 
                    pub_topics = [pub_topics]
                
                for t in pub_topics:
                    if t not in self.subscribed_topics:
                        new_topics.append(t)
                        self.subscribed_topics.add(t)

            # 2. Subscribe to System Topics (Alerts) if not already done
            for key, t in self.base_topics.items():
                # We typically want alerts and status topics
                if 'alert' in key or 'status' in key:
                    if t not in self.subscribed_topics:
                        new_topics.append(t)
                        self.subscribed_topics.add(t)

            # Perform Subscriptions
            if new_topics:
                for t in new_topics:
                    self.client.subscribe(t, qos=0)
                print(f"[StatusService] Subscribed to {len(new_topics)} new topics")
            
        except Exception as e:
            print(f"[StatusService] Error updating subscriptions: {e}")

    def notify(self, topic, payload):
        """MQTT Callback: Store the latest message."""
        try:
            data = json.loads(payload)
            timestamp = time.time()
            device_id = "unknown"

            # Strategy 1: SenML Format (List)
            if isinstance(data, list):
                # Try to find 'bn' (Base Name) which is the device ID
                for item in data:
                    if 'bn' in item:
                        device_id = item['bn']
                        break
            
            # Strategy 2: Dictionary with 'bn'
            elif isinstance(data, dict):
                if 'bn' in data:
                    device_id = data['bn']
                elif 'alert_type' in data:
                    device_id = "system_alert" # Special ID for weather/frost alerts

            # If we couldn't find an ID in the payload, infer from topic
            if device_id == "unknown":
                # Topic format often: project/category/device_id/...
                parts = topic.split('/')
                if len(parts) > 2:
                    # Heuristic: verify against known device IDs if needed, 
                    # or just use the sub-topic that looks like an ID.
                    # For this system: smart_irrigation/farm/field_1/...
                    device_id = f"topic_{parts[-1]}"

            # STORE DATA
            self.latest_data[device_id] = {
                "topic": topic,
                "timestamp": timestamp,
                "received_at": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp)),
                "payload": data
            }
            # print(f"[StatusService] Updated status for {device_id}")

        except Exception as e:
            print(f"[StatusService] Error processing message on {topic}: {e}")

    # ================= REST API =================
    
    @cherrypy.tools.json_out()
    def GET(self, *uri, **params):
        """
        GET / 
        Returns the dictionary of latest statuses.
        """
        return self.latest_data

    def stop(self):
        self.running = False
        self.client.stop()


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
    cherrypy.config.update({'server.socket_host': '0.0.0.0', 'server.socket_port': 9090})

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
        