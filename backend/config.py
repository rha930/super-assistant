import os
from pathlib import Path

from dotenv import load_dotenv

# Load the canonical project-root .env first (matches docker-compose), then allow
# an optional backend/.env to override for local development. Without this, a
# backend/.env would shadow the root .env and silently drop settings like the
# Gemini provider config.
_ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"
_BACKEND_ENV = Path(__file__).resolve().parent / ".env"
load_dotenv(_ROOT_ENV)
if _BACKEND_ENV != _ROOT_ENV:
    load_dotenv(_BACKEND_ENV, override=True)

# Server
FLASK_ENV = os.getenv("FLASK_ENV", "development")
DEBUG = os.getenv("FLASK_DEBUG", "False") == "True"
PORT = int(os.getenv("PORT", 5000))
HOST = os.getenv("HOST", "0.0.0.0")

# Ollama (local model runtime)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4")  # Leave blank to auto-detect from Ollama
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))

# Provider selection ('ollama' local runtime | 'gemini' cloud API)
AGENT_PROVIDER = os.getenv("AGENT_PROVIDER", "ollama")

# Gemini (cloud model runtime) — API key is environment-only, never stored in config
GEMINI_ENABLED = os.getenv("GEMINI_ENABLED", "False") == "True"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "60"))
GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "2048"))
# Comma-separated allow-list of selectable Gemini models.
GEMINI_MODELS = [
    m.strip() for m in os.getenv("GEMINI_MODELS", "gemini-2.5-flash,gemini-2.5-pro").split(",") if m.strip()
]

# Agent Model Defaults
AGENT_MODEL = os.getenv("AGENT_MODEL", OLLAMA_MODEL)
DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))
DEFAULT_MAX_TOKENS = int(os.getenv("DEFAULT_MAX_TOKENS", "1000"))
DEFAULT_TOP_P = float(os.getenv("DEFAULT_TOP_P", "0.9"))
DEFAULT_SYSTEM_PROMPT = os.getenv("DEFAULT_SYSTEM_PROMPT", "You are a helpful AI assistant.")
DEFAULT_MAX_ITERATIONS = int(os.getenv("DEFAULT_MAX_ITERATIONS", "10"))
DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT", "30"))
CONTEXT_MAX_MESSAGES = int(os.getenv("CONTEXT_MAX_MESSAGES", "12"))
CONTEXT_MAX_INPUT_CHARS = int(os.getenv("CONTEXT_MAX_INPUT_CHARS", "12000"))
HISTORY_BACKEND_TYPE = os.getenv("HISTORY_BACKEND_TYPE", "local")
HISTORY_DB_PATH = os.getenv("HISTORY_DB_PATH", "./backend/data/chat_history.db")
HISTORY_MAX_MESSAGES_PER_CONVERSATION = int(os.getenv("HISTORY_MAX_MESSAGES_PER_CONVERSATION", "200"))
HISTORY_REDIS_URL = os.getenv("HISTORY_REDIS_URL", "redis://localhost:6379/0")
HISTORY_REDIS_PREFIX = os.getenv("HISTORY_REDIS_PREFIX", "chat")

# GNews News Articles Tool — API key is environment-only, never stored in config
GNEWS_ENABLED = os.getenv("GNEWS_ENABLED", "False") == "True"
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")
GNEWS_MAX_RESULTS = int(os.getenv("GNEWS_MAX_RESULTS", "5"))  # GNews free tier max: 10
GNEWS_LANGUAGE = os.getenv("GNEWS_LANGUAGE", "en")
GNEWS_COUNTRY = os.getenv("GNEWS_COUNTRY", "us")
GNEWS_TIMEOUT_SECONDS = int(os.getenv("GNEWS_TIMEOUT_SECONDS", "10"))

# Authentication
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "True") == "True"
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "")
AUTH_TOKEN_EXPIRY_HOURS = int(os.getenv("AUTH_TOKEN_EXPIRY_HOURS", "24"))
AUTH_USERS_FILE = os.getenv("AUTH_USERS_FILE", "./users.json")

# Note expansion system prompt
NOTE_EXPANSION_SYSTEM_PROMPT = os.getenv(
    "NOTE_EXPANSION_SYSTEM_PROMPT",
    "You are a note-taking assistant. The user is building a note and will give you short inputs.\n"
    "Your job is to expand their input into well-formatted Markdown content suitable for a note.\n\n"
    "Rules:\n"
    "- Expand short phrases into structured, useful content (lists, headings, paragraphs).\n"
    '- Pre-fill sensible defaults when the topic is common (e.g., "grocery list" -> a list with common items).\n'
    "- Use proper Markdown formatting: headings (#), lists (-), bold (**), etc.\n"
    "- If existing note content is provided, make your addition coherent with it.\n"
    "- Keep expansions concise but useful — aim for practical, actionable content.\n"
    "- Do NOT wrap your response in a code fence. Return raw Markdown only.\n"
    '- Do NOT include preamble like "Here\'s your expanded note:". Just return the content.',
)

# Default Config
DEFAULT_CONFIG = {
    "provider": AGENT_PROVIDER,
    "model": AGENT_MODEL,
    "model_parameters": {
        "temperature": DEFAULT_TEMPERATURE,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "top_p": DEFAULT_TOP_P,
    },
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
    "agent_config": {
        "max_iterations": DEFAULT_MAX_ITERATIONS,
        "timeout": DEFAULT_TIMEOUT,
    },
    "context_config": {
        "max_messages": CONTEXT_MAX_MESSAGES,
        "max_input_chars": CONTEXT_MAX_INPUT_CHARS,
    },
    "history_config": {
        "backend_type": HISTORY_BACKEND_TYPE,
        "db_path": HISTORY_DB_PATH,
        "max_messages_per_conversation": HISTORY_MAX_MESSAGES_PER_CONVERSATION,
        "redis_url": HISTORY_REDIS_URL,
        "redis_prefix": HISTORY_REDIS_PREFIX,
    },
    "gemini": {
        "enabled": GEMINI_ENABLED,
        "model": GEMINI_MODEL,
        "base_url": GEMINI_BASE_URL,
        "timeout_seconds": GEMINI_TIMEOUT_SECONDS,
        "max_output_tokens": GEMINI_MAX_OUTPUT_TOKENS,
        "models": GEMINI_MODELS,
    },
    "gnews": {
        "enabled": GNEWS_ENABLED,
        "max_results": GNEWS_MAX_RESULTS,
        "language": GNEWS_LANGUAGE,
        "country": GNEWS_COUNTRY,
        "timeout_seconds": GNEWS_TIMEOUT_SECONDS,
        # GNEWS_API_KEY is never stored here — read from env at runtime only
    },
}
