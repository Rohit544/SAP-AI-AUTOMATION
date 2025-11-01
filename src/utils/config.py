import os
import yaml
from typing import Any, Dict, Optional
from pathlib import Path

class ConfigManager:
    """Centralized configuration management"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._override_from_env()
    
    def _load_config(self) -> Dict:
        """Load configuration from YAML"""
        if not self.config_path.exists():
            return {}
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    
    def _override_from_env(self):
        """Override config with environment variables"""
        # Example: FI_COMPANY_CODE env var overrides FI.company_code
        for key, value in os.environ.items():
            if key.startswith('SAP_'):
                config_key = key.replace('SAP_', '').replace('_', '.').lower()
                self._set_nested(self.config, config_key, value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value using dot notation"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        
        return value if value is not None else default
    
    def get_dict(self, key: str) -> Dict:
        """Get nested dictionary"""
        result = self.get(key, {})
        return result if isinstance(result, dict) else {}