import json
import os
import cherrypy


class CatalogueService:
    exposed = True

    def __init__(self, file_path):
        self.file_path = file_path
        self.data = self.load()
        print(f"[Catalogue] Loaded {len(self.data.get('devices', []))} devices")

    def load(self):
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Config not found: {self.file_path}")
        with open(self.file_path, "r") as f:
            return json.load(f)

    @cherrypy.tools.json_out()
    def GET(self, *uri, **params):
        if len(uri) == 0:
            return self.data
        elif uri[0] == "broker":
            return self.data.get("broker", {})
        elif uri[0] == "devices":
            return self.data.get("devices", [])
        elif uri[0] == "settings":
            return self.data.get("settings", {})
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