import json
import os
import time
import cherrypy


class CatalogueService:
    """
    Device/Service Catalogue - Central Registry
    
    Supports multiple gardens, each with their own fields.
    Provides REST API for:
    - GET: Retrieve configuration, devices, broker info, gardens
    - POST: Register new devices/services (with dynamic ID assignment)
    - PUT: Update device heartbeat/timestamp
    - DELETE: Unregister devices
    """
    exposed = True

    def __init__(self, file_path):
        self.file_path = file_path
        self.data = self.load()
        
        # Initialize device counters if missing
        if 'device_counters' not in self.data:
            self.data['device_counters'] = {'sensor': 0, 'actuator': 0}
        
        print(f"[Catalogue] Loaded {len(self.data.get('devices', []))} devices")
        print(f"[Catalogue] Gardens: {list(self.data.get('gardens', {}).keys())}")

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

    def generate_device_id(self, device_type, garden_id, field_id):
        """
        Generate a unique device ID based on type, garden, and field.
        Format: sensor_garden1_field1_001 or actuator_garden1_field1_001
        """
        # Increment counter for this device type
        counter = self.data['device_counters'].get(device_type, 0) + 1
        self.data['device_counters'][device_type] = counter
        
        # Build ID
        device_id = f"{device_type}_{garden_id}_{field_id}_{counter:03d}"
        return device_id

    # ==================== GET ====================
    @cherrypy.tools.json_out()
    def GET(self, *uri, **params):
        """
        GET endpoints:
        - /              : Full configuration
        - /broker        : MQTT broker details
        - /devices       : List of all devices
        - /devices/<id>  : Specific device by ID
        - /settings      : System settings
        - /services      : List of registered services
        - /gardens       : List of all gardens
        - /gardens/<id>  : Specific garden by ID
        - /gardens/<id>/fields : Fields in a garden
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
            return self.data.get("services_list", [])
        
        elif uri[0] == "gardens":
            gardens = self.data.get("gardens", {})
            if len(uri) == 1:
                # Return list of gardens with their info
                return gardens
            elif len(uri) == 2:
                # GET /gardens/<garden_id>
                garden_id = uri[1]
                if garden_id in gardens:
                    return gardens[garden_id]
                else:
                    raise cherrypy.HTTPError(404, f"Garden {garden_id} not found")
            elif len(uri) == 3 and uri[2] == "fields":
                # GET /gardens/<garden_id>/fields
                garden_id = uri[1]
                if garden_id in gardens:
                    return gardens[garden_id].get("fields", {})
                else:
                    raise cherrypy.HTTPError(404, f"Garden {garden_id} not found")
        
        else:
            raise cherrypy.HTTPError(404, "Not found")

    # ==================== POST ====================
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self, *uri, **params):
        """
        POST endpoints:
        - /devices   : Register a new device (ID assigned by Catalogue if not provided)
        - /services  : Register a new service
        
        Device payload (new - ID generated): 
        {"type": "sensor", "garden_id": "garden_1", "field_id": "field_1", "name": "..."}
        
        Device payload (with ID - heartbeat/update):
        {"id": "sensor_garden1_field1_001"}
        
        Service payload: {"id": "...", "name": "...", "endpoint": "..."}
        """
        payload = cherrypy.request.json
        
        if len(uri) == 1 and uri[0] == "devices":
            # Case 1: Device with ID exists -> heartbeat update
            if "id" in payload:
                device_id = payload["id"]
                idx, existing = self.find_device(device_id)
                
                if existing:
                    # Device exists -> update timestamp (heartbeat)
                    self.data["devices"][idx]["last_seen"] = time.time()
                    self.data["devices"][idx]["status"] = "online"
                    print(f"[Catalogue] Device '{device_id}' heartbeat")
                    return {"status": "updated", "id": device_id}
                else:
                    # Device has ID but not registered -> register with given ID
                    new_device = {
                        "id": device_id,
                        "name": payload.get("name", device_id),
                        "type": payload.get("type", "unknown"),
                        "garden_id": payload.get("garden_id", "garden_1"),
                        "field_id": payload.get("field_id", "field_1"),
                        "topics": payload.get("topics", {}),
                        "last_seen": time.time(),
                        "status": "online"
                    }
                    self.data["devices"].append(new_device)
                    self.save()
                    print(f"[Catalogue] Device '{device_id}' registered")
                    return {"status": "registered", "id": device_id}
            
            # Case 2: New device without ID -> generate ID dynamically
            else:
                device_type = payload.get("type", "sensor")
                garden_id = payload.get("garden_id", "garden_1")
                field_id = payload.get("field_id", "field_1")
                
                # Validate garden exists
                gardens = self.data.get("gardens", {})
                if garden_id not in gardens:
                    raise cherrypy.HTTPError(400, f"Garden '{garden_id}' not found")
                
                # Generate unique ID
                device_id = self.generate_device_id(device_type, garden_id, field_id)
                
                # Build topic prefix based on garden and field
                topic_prefix = self.data.get("project_info", {}).get("topic_prefix", "smart_irrigation")
                
                # Generate topics based on device type
                if device_type == "sensor":
                    topics = {
                        "publish": [
                            f"{topic_prefix}/farm/{garden_id}/{field_id}/soil_moisture",
                            f"{topic_prefix}/farm/{garden_id}/{field_id}/temperature"
                        ],
                        "subscribe": []
                    }
                elif device_type == "actuator":
                    topics = {
                        "publish": [f"{topic_prefix}/farm/{garden_id}/{field_id}/valve_status"],
                        "subscribe": [f"{topic_prefix}/farm/{garden_id}/{field_id}/valve_cmd"]
                    }
                else:
                    topics = payload.get("topics", {})
                
                # Create new device entry
                new_device = {
                    "id": device_id,
                    "name": payload.get("name", f"{device_type.title()} {garden_id} {field_id}"),
                    "type": device_type,
                    "garden_id": garden_id,
                    "field_id": field_id,
                    "topics": topics,
                    "last_seen": time.time(),
                    "status": "online"
                }
                
                self.data["devices"].append(new_device)
                self.save()
                print(f"[Catalogue] Device '{device_id}' registered (new ID generated)")
                
                # Return full device info including generated ID and topics
                return {
                    "status": "registered",
                    "id": device_id,
                    "topics": topics,
                    "garden_id": garden_id,
                    "field_id": field_id
                }
        
        elif len(uri) == 1 and uri[0] == "services":
            # Register a service
            if "id" not in payload:
                raise cherrypy.HTTPError(400, "Missing 'id' field")
            
            if "services_list" not in self.data:
                self.data["services_list"] = []
            
            service_id = payload["id"]
            
            # Check if service already exists
            for i, s in enumerate(self.data["services_list"]):
                if s["id"] == service_id:
                    # Update existing
                    self.data["services_list"][i]["last_seen"] = time.time()
                    self.data["services_list"][i]["status"] = "online"
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
            self.data["services_list"].append(new_service)
            print(f"[Catalogue] Service '{service_id}' registered")
            return {"status": "registered", "id": service_id}
        
        elif len(uri) == 1 and uri[0] == "gardens":
            # Register a new garden
            if "id" not in payload:
                raise cherrypy.HTTPError(400, "Missing 'id' field for garden")
            
            garden_id = payload["id"]
            
            if "gardens" not in self.data:
                self.data["gardens"] = {}
            
            if garden_id in self.data["gardens"]:
                # Update existing garden
                self.data["gardens"][garden_id].update({
                    "name": payload.get("name", self.data["gardens"][garden_id].get("name")),
                    "location": payload.get("location", self.data["gardens"][garden_id].get("location", {})),
                    "last_seen": time.time()
                })
                print(f"[Catalogue] Garden '{garden_id}' updated")
                return {"status": "updated", "id": garden_id}
            else:
                # New garden
                self.data["gardens"][garden_id] = {
                    "name": payload.get("name", f"Garden {garden_id}"),
                    "location": payload.get("location", {}),
                    "fields": payload.get("fields", {}),
                    "last_seen": time.time()
                }
                self.save()
                print(f"[Catalogue] Garden '{garden_id}' registered")
                return {"status": "registered", "id": garden_id}
        
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
