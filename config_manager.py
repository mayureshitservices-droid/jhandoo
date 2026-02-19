import json
import os

CONFIG_FILE = "config.json"

class ConfigManager:
    @staticmethod
    def load_config():
        """Load configuration from JSON file."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    @staticmethod
    def save_config(config_data):
        """Save configuration to JSON file."""
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)

    @staticmethod
    def get_setting(key, default=None):
        """Get a specific setting value."""
        config = ConfigManager.load_config()
        return config.get(key, default)
