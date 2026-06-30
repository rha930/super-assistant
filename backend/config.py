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
HISTORY_BACKEND_TYPE = os.getenv('HISTORY_BACKEND_TYPE', 'local')
HISTORY_DB_PATH = os.getenv('HISTORY_DB_PATH', './backend/data/chat_history.db')
HISTORY_MAX_MESSAGES_PER_CONVERSATION = int(os.getenv('HISTORY_MAX_MESSAGES_PER_CONVERSATION', '200'))
HISTORY_REDIS_URL = os.getenv('HISTORY_REDIS_URL', 'redis://localhost:6379/0')
HISTORY_REDIS_PREFIX = os.getenv('HISTORY_REDIS_PREFIX', 'chat')

# Authentication
AUTH_ENABLED = os.getenv('AUTH_ENABLED', 'True') == 'True'
AUTH_SECRET_KEY = os.getenv('AUTH_SECRET_KEY', '')
AUTH_TOKEN_EXPIRY_HOURS = int(os.getenv('AUTH_TOKEN_EXPIRY_HOURS', '24'))
AUTH_USERS_FILE = os.getenv('AUTH_USERS_FILE', './users.json')

# Web Search Tool
WEB_SEARCH_ENABLED = os.getenv('WEB_SEARCH_ENABLED', 'True') == 'True'
WEB_SEARCH_MAX_RESULTS = int(os.getenv('WEB_SEARCH_MAX_RESULTS', '5'))
WEB_SEARCH_TIMEOUT = int(os.getenv('WEB_SEARCH_TIMEOUT', '10'))

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
    },
    'history_config': {
        'backend_type': HISTORY_BACKEND_TYPE,
        'db_path': HISTORY_DB_PATH,
        'max_messages_per_conversation': HISTORY_MAX_MESSAGES_PER_CONVERSATION,
        'redis_url': HISTORY_REDIS_URL,
        'redis_prefix': HISTORY_REDIS_PREFIX
    },
    'tools': {
        'web_search': {
            'enabled': WEB_SEARCH_ENABLED,
            'max_results': WEB_SEARCH_MAX_RESULTS
        }
    }
}
