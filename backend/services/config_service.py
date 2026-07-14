import copy
import logging
from typing import Any

from config import AGENT_MODEL, DEFAULT_CONFIG, GEMINI_API_KEY, OLLAMA_MODEL

from services.gemini_service import GeminiService

logger = logging.getLogger(__name__)


class ConfigService:
    """Service for managing configuration."""

    def __init__(self):
        self.config = copy.deepcopy(DEFAULT_CONFIG)

    def _gemini_available(self) -> bool:
        """Whether the Gemini provider can currently be selected."""
        gemini = GeminiService(self.config.get("gemini", {}), api_key=GEMINI_API_KEY)
        return gemini.is_available()

    def get_config(self) -> dict[str, Any]:
        """Get current configuration."""
        resolved = copy.deepcopy(self.config)
        resolved["provider"] = (resolved.get("provider") or "ollama").strip().lower()
        model = (resolved.get("model") or "").strip()
        if not model:
            resolved["model"] = (AGENT_MODEL or OLLAMA_MODEL or "").strip()
        return resolved

    def update_config(self, new_config: dict[str, Any]) -> dict[str, Any]:
        """
        Update configuration.

        Args:
            new_config: New configuration values

        Returns:
            Updated configuration
        """
        try:
            # Update provider selection (allow-list only)
            if "provider" in new_config:
                provider = str(new_config.get("provider") or "ollama").strip().lower()
                if provider not in ("ollama", "gemini"):
                    raise ValueError(f"Invalid provider '{provider}'. Must be 'ollama' or 'gemini'.")
                if provider == "gemini" and not self._gemini_available():
                    raise ValueError("Gemini provider is not available. Configure GEMINI_ENABLED and GEMINI_API_KEY.")
                self.config["provider"] = provider

            # Update active model
            if "model" in new_config:
                model = str(new_config.get("model") or "").strip()
                self.config["model"] = model
                # Keep the gemini sub-config in sync so GeminiService sees the
                # user-selected model when constructed via _build_gemini_service.
                current_provider = self.config.get("provider", "ollama")
                if current_provider == "gemini" and "gemini" in self.config:
                    self.config["gemini"]["model"] = model

            # Validate and update model parameters
            if "model_parameters" in new_config:
                params = new_config["model_parameters"]
                self.config["model_parameters"].update(params)

            # Update system prompt
            if "system_prompt" in new_config:
                self.config["system_prompt"] = new_config["system_prompt"]

            # Update agent config
            if "agent_config" in new_config:
                self.config["agent_config"].update(new_config["agent_config"])

            # Update context config
            if "context_config" in new_config:
                if "context_config" not in self.config:
                    self.config["context_config"] = {}
                self.config["context_config"].update(new_config["context_config"])

            # Update history config
            if "history_config" in new_config:
                if "history_config" not in self.config:
                    self.config["history_config"] = {}
                self.config["history_config"].update(new_config["history_config"])

            logger.info("Configuration updated successfully")
            return self.get_config()

        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            raise

    def reset_config(self) -> dict[str, Any]:
        """Reset configuration to defaults."""
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        logger.info("Configuration reset to defaults")
        return copy.deepcopy(self.config)


_config_service_instance: "ConfigService | None" = None


def get_config_service() -> "ConfigService":
    """Return the shared ConfigService singleton.

    Both the config routes and the ChatService use this so configuration
    changes (provider, model, etc.) take effect on subsequent chats.
    """
    global _config_service_instance
    if _config_service_instance is None:
        _config_service_instance = ConfigService()
    return _config_service_instance
