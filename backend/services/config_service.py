import logging
from typing import Dict, Any
from config import DEFAULT_CONFIG, AGENT_MODEL, OLLAMA_MODEL
import copy

logger = logging.getLogger(__name__)

class ConfigService:
    """Service for managing configuration."""
    
    def __init__(self):
        self.config = copy.deepcopy(DEFAULT_CONFIG)
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        resolved = copy.deepcopy(self.config)
        model = (resolved.get('model') or '').strip()
        if not model:
            resolved['model'] = (AGENT_MODEL or OLLAMA_MODEL or '').strip()
        return resolved
    
    def update_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update configuration.
        
        Args:
            new_config: New configuration values
        
        Returns:
            Updated configuration
        """
        try:
            # Update active model
            if 'model' in new_config:
                model = str(new_config.get('model') or '').strip()
                self.config['model'] = model

            # Validate and update model parameters
            if 'model_parameters' in new_config:
                params = new_config['model_parameters']
                self.config['model_parameters'].update(params)
            
            # Update system prompt
            if 'system_prompt' in new_config:
                self.config['system_prompt'] = new_config['system_prompt']
            
            # Update agent config
            if 'agent_config' in new_config:
                self.config['agent_config'].update(new_config['agent_config'])

            # Update context config
            if 'context_config' in new_config:
                if 'context_config' not in self.config:
                    self.config['context_config'] = {}
                self.config['context_config'].update(new_config['context_config'])
            
            logger.info("Configuration updated successfully")
            return self.get_config()
        
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            raise
    
    def reset_config(self) -> Dict[str, Any]:
        """Reset configuration to defaults."""
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        logger.info("Configuration reset to defaults")
        return copy.deepcopy(self.config)
