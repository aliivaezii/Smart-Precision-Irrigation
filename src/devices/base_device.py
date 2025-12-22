class BaseDevice:
    
    
    def __init__(self, device_id, device_type):
        self.device_id = device_id
        self.device_type = device_type
        self.is_running = False

    def start(self):
        self.is_running = True

    def stop(self):
        self.is_running = False

    def get_status(self):
        return {
            'id': self.device_id,
            'type': self.device_type,
            'running': self.is_running
        }