import json
import os
import time
import cherrypy


class CatalogueService:
    """
    Device/Service Catalogue - Central Registry
    
    Provides REST API for:
    - GET: Retrieve configuration, devices, broker info
    - POST: Register new devices/services
    - PUT: Update device heartbeat/timestamp
    - DELETE: Unregister devices
    """
    exposed = True

    def __init__(self, file_path):
        self.file_path = file_path
        self.data = self.load()
        print(f"[Catalogue] Loaded {len(self.data.get('devices', []))} devices")

    def load(self):
        """Load configuration from JSON file."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Config not found: {self.file_path}")
        with open(self.file_path, "r") as f:
            return json.load(f)

    def save(self):
        """Save current configuration to JSON file."""
        with open(self.file_path, "w") as f:
            json.dump(self.data, f, indent=4)
        print("[Catalogue] Configuration saved")

    def find_device(self, device_id):
        """Find a device by ID. Returns (index, device) or (-1, None)."""
        for i, d in enumerate(self.data.get("devices", [])):
            if d["id"] == device_id:
                return i, d
        return -1, None

    # ==================== GET ====================
    @cherrypy.tools.json_out()
    def GET(self, *uri, **params):
        """
        GET endpoints:
        - /           : Full configuration
        - /broker     : MQTT broker details
        - /devices    : List of all devices
        - /devices/<id> : Specific device by ID
        - /settings   : System settings
        - /services   : List of registered services
        """
        if len(uri) == 0:
            return self.data
        
        elif uri[0] == "broker":
            return self.data.get("broker", {})
        
        elif uri[0] == "devices":
            if len(uri) == 1:
                return self.data.get("devices", [])
            else:
                # GET /devices/<device_id>
                device_id = uri[1]
                idx, device = self.find_device(device_id)
                if device:
                    return device
                else:
                    raise cherrypy.HTTPError(404, f"Device {device_id} not found")
        
        elif uri[0] == "settings":
            return self.data.get("settings", {})
        
        elif uri[0] == "services":
            return self.data.get("services", [])
        
        else:
            raise cherrypy.HTTPError(404, "Not found")

    # ==================== POST ====================
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self, *uri, **params):
        """
        POST endpoints:
        - /devices   : Register a new device
        - /services  : Register a new service
        
        Device payload: {"id": "...", "name": "...", "type": "...", "topics": {...}}
        Service payload: {"id": "...", "name": "...", "endpoint": "..."}
        """
        payload = cherrypy.request.json
        
        if len(uri) == 1 and uri[0] == "devices":
            # Validate required fields
            if "id" not in payload:
                raise cherrypy.HTTPError(400, "Missing 'id' field")
            
            device_id = payload["id"]
            idx, existing = self.find_device(device_id)
            
            if existing:
                # Device exists -> update timestamp (like a heartbeat)
                self.data["devices"][idx]["last_seen"] = time.time()
                self.data["devices"][idx]["status"] = "online"
                print(f"[Catalogue] Device '{device_id}' updated (heartbeat)")
                return {"status": "updated", "id": device_id}
            else:
                # New device -> append to list
                new_device = {
                    "id": payload.get("id"),
                    "name": payload.get("name", "Unknown"),
                    "type": payload.get("type", "unknown"),
                    "topics": payload.get("topics", {}),
                    "last_seen": time.time(),
                    "status": "online"
                }
                self.data["devices"].append(new_device)
                self.save()
                print(f"[Catalogue] Device '{device_id}' registered")
                return {"status": "registered", "id": device_id}
        
        elif len(uri) == 1 and uri[0] == "services":
            # Register a service
            if "id" not in payload:
                raise cherrypy.HTTPError(400, "Missing 'id' field")
            
            if "services" not in self.data:
                self.data["services"] = []
            
            service_id = payload["id"]
            
            # Check if service already exists
            for i, s in enumerate(self.data["services"]):
                if s["id"] == service_id:
                    # Update existing
                    self.data["services"][i]["last_seen"] = time.time()
                    self.data["services"][i]["status"] = "online"
                    print(f"[Catalogue] Service '{service_id}' updated")
                    return {"status": "updated", "id": service_id}
            
            # New service
            new_service = {
                "id": payload.get("id"),
                "name": payload.get("name", "Unknown Service"),
                "endpoint": payload.get("endpoint", ""),
                "last_seen": time.time(),
                "status": "online"
            }
            self.data["services"].append(new_service)
            print(f"[Catalogue] Service '{service_id}' registered")
            return {"status": "registered", "id": service_id}
        
        else:
            raise cherrypy.HTTPError(404, "Not found")

    # ==================== PUT ====================
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def PUT(self, *uri, **params):
        """
        PUT endpoints:
        - /devices/<id> : Update device info/heartbeat
        
        Payload: {"status": "online", ...}
        """
        if len(uri) == 2 and uri[0] == "devices":
            device_id = uri[1]
            idx, device = self.find_device(device_id)
            
            if device is None:
                raise cherrypy.HTTPError(404, f"Device {device_id} not found")
            
            payload = cherrypy.request.json
            
            # Update allowed fields
            if "name" in payload:
                self.data["devices"][idx]["name"] = payload["name"]
            if "topics" in payload:
                self.data["devices"][idx]["topics"] = payload["topics"]
            if "status" in payload:
                self.data["devices"][idx]["status"] = payload["status"]
            
            # Always update timestamp
            self.data["devices"][idx]["last_seen"] = time.time()
            
            print(f"[Catalogue] Device '{device_id}' updated")
            return {"status": "updated", "id": device_id}
        
        else:
            raise cherrypy.HTTPError(404, "Not found")

    # ==================== DELETE ====================
    @cherrypy.tools.json_out()
    def DELETE(self, *uri, **params):
        """
        DELETE endpoints:
        - /devices/<id> : Unregister a device
        """
        if len(uri) == 2 and uri[0] == "devices":
            device_id = uri[1]
            idx, device = self.find_device(device_id)
            
            if device is None:
                raise cherrypy.HTTPError(404, f"Device {device_id} not found")
            
            del self.data["devices"][idx]
            self.save()
            print(f"[Catalogue] Device '{device_id}' removed")
            return {"status": "removed", "id": device_id}
        
        else:
            raise cherrypy.HTTPError(404, "Not found")


if __name__ == "__main__":
    # Find config file path
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    config_path = os.path.join(base_dir, "config", "system_config.json")

    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True,
        }
    }

    cherrypy.tree.mount(CatalogueService(config_path), "/", conf)
    cherrypy.config.update({"server.socket_host": "0.0.0.0", "server.socket_port": 8080})
    
    print("Catalogue Service running on http://0.0.0.0:8080")
    cherrypy.engine.start()
    cherrypy.engine.block()
