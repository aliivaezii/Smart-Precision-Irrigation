import cherrypy
import json
import os
import sys

class CatalogueService:
    exposed = True

    def __init__(self):
        self.config_path = self._find_config()
        self.data = self._load_config()

    def _find_config(self):
        # Professional path finding (Mac/Windows compatible)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        return os.path.join(base_dir, "config", "system_config.json")

    def _load_config(self):
        with open(self.config_path, "r") as f:
            return json.load(f)

    @cherrypy.tools.json_out()
    def GET(self, *uri, **params):
        # 1. GET / -> Return whole config
        if not uri:
            return self.data
        
        # 2. GET /broker -> Return just broker info
        if uri[0] == "broker":
            return self.data["broker"]
        
        # 3. GET /devices -> Return list of devices
        if uri[0] == "devices":
            return self.data["devices"]
        
        return cherrypy.HTTPError(404, "Endpoint not found")

if __name__ == "__main__":
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True,
        }
    }
    cherrypy.tree.mount(CatalogueService(), "/", conf)
    cherrypy.config.update({'server.socket_host': '0.0.0.0', 'server.socket_port': 8080})
    cherrypy.engine.start()
    cherrypy.engine.block()