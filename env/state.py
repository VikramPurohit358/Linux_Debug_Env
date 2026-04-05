"""System state representation."""


class SystemState:
    """Represents Linux system state (files, services, ports, environment)."""
    
    # Initial state defaults
    INITIAL_STATE = {
        'files': {
            '/etc/app.conf': 'PORT=9999',
            '/var/log/app.log': 'ERROR: Service failed to start',
        },
        'services': {
            'app': 'stopped',
        },
        'ports': {
            8080: 'free',
            9999: 'occupied',
        },
        'env_vars': {},
    }
    
    def __init__(self):
        """Initialize state with default values."""
        self.reset()
    
    def reset(self):
        """Reset state to initial values."""
        # Deep copy to avoid mutation
        self.files = dict(self.INITIAL_STATE['files'])
        self.services = dict(self.INITIAL_STATE['services'])
        self.ports = dict(self.INITIAL_STATE['ports'])
        self.env_vars = dict(self.INITIAL_STATE['env_vars'])
    
    def get_state(self):
        """Get current state as dict."""
        return {
            'files': self.files.copy(),
            'services': self.services.copy(),
            'ports': self.ports.copy(),
            'env_vars': self.env_vars.copy(),
        }
    
    def update_file(self, path, content):
        """Update or create file with content."""
        self.files[path] = content
    
    def update_service(self, service, status):
        """Update service status (running/stopped)."""
        if status not in ('running', 'stopped'):
            raise ValueError(f"Invalid service status: {status}")
        self.services[service] = status
    
    def update_port(self, port, status):
        """Update port status (free/occupied)."""
        if status not in ('free', 'occupied'):
            raise ValueError(f"Invalid port status: {status}")
        self.ports[port] = status
    
    def update_env(self, key, value):
        """Update environment variable."""
        self.env_vars[key] = value
    
    def to_dict(self):
        """Convert state to dict (same as get_state)."""
        return self.get_state()
