"""
Server configuration module.
"""
import json
from pathlib import Path
from typing import Dict, Any

class ServerConfig:
    """
    Manages server configuration including optional features like invites.
    """
    _instance = None
    _config_file = Path('server_config.json')
    _default_config = {
        'require_invites': True,  # Whether invites are required for registration
        'invite_expiry_days': 7,  # Number of days until an invite expires
        'max_players': 100,       # Maximum number of players
        'port': 5001,             # Server port
        'host': 'localhost',      # Server host
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServerConfig, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        """Load configuration from file or create with defaults."""
        if self._config_file.exists():
            try:
                with open(self._config_file, 'r') as f:
                    self._config = {**self._default_config, **json.load(f)}
            except (json.JSONDecodeError, OSError):
                self._config = self._default_config.copy()
                self._save_config()
        else:
            self._config = self._default_config.copy()
            self._save_config()

    def _save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self._config_file, 'w') as f:
                json.dump(self._config, f, indent=4)
        except OSError as e:
            print(f"Warning: Could not save server config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value and save to file."""
        if key in self._default_config:
            self._config[key] = value
            self._save_config()
        else:
            raise KeyError(f"Invalid config key: {key}")

    @property
    def require_invites(self) -> bool:
        """Whether invites are required for registration."""
        return self.get('require_invites', True)

    @require_invites.setter
    def require_invites(self, value: bool) -> None:
        """Set whether invites are required for registration."""
        self.set('require_invites', bool(value))

# Global instance
config = ServerConfig()
