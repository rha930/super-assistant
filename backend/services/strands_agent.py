import logging
from typing import Dict, Any, Optional, Generator
import requests
import os
import json

logger = logging.getLogger(__name__)

# Import with fallback defaults
try:
    from config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS
except ImportError:
    OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma4')
    OLLAMA_TIMEOUT_SECONDS = int(os.getenv('OLLAMA_TIMEOUT_SECONDS', '120'))

class StrandsAgentService:
    """Service for interacting with a localhosted Ollama model."""
    
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the local Ollama service client.
        
        Args:
            base_url: Ollama server base URL (defaults to OLLAMA_BASE_URL env or config)
            model: Default model name (defaults to OLLAMA_MODEL env or config)
        """
        self.base_url = (base_url or OLLAMA_BASE_URL or 'http://localhost:11434').rstrip('/')
        self.model = model or OLLAMA_MODEL or 'gemma4'
        logger.info("Ollama service initialized at %s with model %s", self.base_url, self.model)

    def _build_prompt(self, user_message: str, system_prompt: Optional[str] = None) -> str:
        if system_prompt:
            return f"System: {system_prompt}\n\nUser: {user_message}\nAssistant:"
        return user_message

    def stream_agent(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Generator[Dict[str, Any], None, None]:
        """Stream response chunks from Ollama /api/generate."""
        try:
            model = kwargs.get('model', self.model)
            prompt = self._build_prompt(user_message, system_prompt)

            options = {
                'temperature': kwargs.get('temperature', 0.7),
                'top_p': kwargs.get('top_p', 0.9),
                'num_predict': kwargs.get('max_tokens', 1000)
            }

            payload = {
                'model': model,
                'prompt': prompt,
                'stream': True,
                'options': options
            }

            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=OLLAMA_TIMEOUT_SECONDS,
                stream=True
            )
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue

                data = json.loads(line)
                chunk = data.get('response', '')
                done = bool(data.get('done', False))

                if chunk:
                    yield {
                        'chunk': chunk,
                        'done': False,
                        'metadata': {
                            'model': model,
                            'tool_calls': []
                        }
                    }

                if done:
                    yield {
                        'chunk': '',
                        'done': True,
                        'metadata': {
                            'tokens_used': data.get('eval_count', 0),
                            'tool_calls': [],
                            'model': model,
                            'total_duration_ns': data.get('total_duration', 0)
                        }
                    }
                    break

        except requests.exceptions.ConnectionError as e:
            msg = f"Failed to connect to Ollama at {self.base_url}. Make sure Ollama is running: {str(e)}"
            logger.error(msg)
            raise RuntimeError(msg) from e
        except requests.exceptions.Timeout as e:
            msg = f"Ollama request timed out after {OLLAMA_TIMEOUT_SECONDS}s at {self.base_url}"
            logger.error(msg)
            raise RuntimeError(msg) from e
        except Exception as e:
            logger.error("Error invoking Ollama model at %s: %s", self.base_url, e)
            raise
    
    def invoke_agent(
        self,
        agent_id: Optional[str],
        session_id: Optional[str],
        user_message: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Invoke the Strands agent with a user message.
        
        Args:
            agent_id: Unused placeholder for compatibility
            session_id: Unused placeholder for compatibility
            user_message: User input message
            system_prompt: Optional system prompt override
            **kwargs: Additional generation parameters (temperature, top_p, max_tokens, model)
        
        Returns:
            Agent response and metadata
        """
        full_text = ''
        metadata: Dict[str, Any] = {'tool_calls': []}

        for event in self.stream_agent(
            user_message=user_message,
            system_prompt=system_prompt,
            **kwargs
        ):
            if event.get('chunk'):
                full_text += event['chunk']
            if event.get('done'):
                metadata = event.get('metadata', metadata)

        return {
            'response': full_text,
            'metadata': metadata
        }
