import os
import yaml
from pathlib import Path
from scribe.utils.paths import get_config_dir

class ConfigManager:
    """Manages application configuration via YAML."""
    
    DEFAULT_CONFIG = {
        "transcription": {
            "min_duration": 60,
            "max_duration": 90,
            "silence_threshold": 0.01,
            "silence_duration": 0.5,
            "max_silent_chunks": 1,
            "silence_chunk_threshold": 0.005
        },
        "synthesis": {
            "ollama_model": "qwen3:8b",
            "logseq_graph_path": ""
        }
    }

    def __init__(self):
        self.config_dir = get_config_dir()
        self.config_path = self.config_dir / "config.yaml"
        self.config = self.load_config()

    def load_config(self):
        """Load config from file or create default if missing."""
        if not self.config_path.exists():
            self.save_config(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
                
            # Merge with defaults to ensure all keys exist
            merged_config = self.DEFAULT_CONFIG.copy()
            
            # Deep merge for nested dictionaries
            for section, values in user_config.items():
                if section in merged_config and isinstance(merged_config[section], dict):
                    merged_config[section].update(values)
                else:
                    merged_config[section] = values
                    
            return merged_config
            
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.DEFAULT_CONFIG.copy()

    def save_config(self, config_data):
        """Save configuration to file."""
        try:
            if not self.config_dir.exists():
                os.makedirs(self.config_dir)
                
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
                
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, section, key, default=None):
        """Get a config value safely."""
        return self.config.get(section, {}).get(key, default)
