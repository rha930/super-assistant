import os
from dotenv import load_dotenv

load_dotenv()

# Server
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
DEBUG = os.getenv('FLASK_DEBUG', 'False') == 'True'
PORT = int(os.getenv('PORT', 5000))
HOST = os.getenv('HOST', '0.0.0.0')

# Ollama (local model runtime)
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma4')  # Leave blank to auto-detect from Ollama
OLLAMA_TIMEOUT_SECONDS = int(os.getenv('OLLAMA_TIMEOUT_SECONDS', '120'))

# Agent Model Defaults
AGENT_MODEL = os.getenv('AGENT_MODEL', OLLAMA_MODEL)
DEFAULT_TEMPERATURE = float(os.getenv('DEFAULT_TEMPERATURE', '0.7'))
DEFAULT_MAX_TOKENS = int(os.getenv('DEFAULT_MAX_TOKENS', '1000'))
DEFAULT_TOP_P = float(os.getenv('DEFAULT_TOP_P', '0.9'))
DEFAULT_SYSTEM_PROMPT = os.getenv('DEFAULT_SYSTEM_PROMPT', 'You are a helpful AI assistant.')
DEFAULT_MAX_ITERATIONS = int(os.getenv('DEFAULT_MAX_ITERATIONS', '10'))
DEFAULT_TIMEOUT = int(os.getenv('DEFAULT_TIMEOUT', '30'))
CONTEXT_MAX_MESSAGES = int(os.getenv('CONTEXT_MAX_MESSAGES', '12'))
CONTEXT_MAX_INPUT_CHARS = int(os.getenv('CONTEXT_MAX_INPUT_CHARS', '12000'))

# Default Config
DEFAULT_CONFIG = {
    'model': AGENT_MODEL,
    'model_parameters': {
        'temperature': DEFAULT_TEMPERATURE,
        'max_tokens': DEFAULT_MAX_TOKENS,
        'top_p': DEFAULT_TOP_P
    },
    'system_prompt': DEFAULT_SYSTEM_PROMPT,
    'agent_config': {
        'max_iterations': DEFAULT_MAX_ITERATIONS,
        'timeout': DEFAULT_TIMEOUT
    },
    'context_config': {
        'max_messages': CONTEXT_MAX_MESSAGES,
        'max_input_chars': CONTEXT_MAX_INPUT_CHARS
    }
}
