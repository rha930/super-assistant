import logging
import re

import requests
from config import OLLAMA_BASE_URL, OLLAMA_MODEL
from flask import Blueprint
from models.response import ErrorResponse, SuccessResponse

logger = logging.getLogger(__name__)
health_bp = Blueprint('health', __name__, url_prefix='/api')

# Model names must be printable, reasonable length, no control chars.
_MODEL_NAME_RE = re.compile(r'^[\w.:/-]{1,128}$')


def _sanitize_model_name(raw: str) -> str | None:
    """Return the model name if it passes validation, else None."""
    name = raw.strip()
    if _MODEL_NAME_RE.match(name):
        return name
    return None

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return SuccessResponse(
        message='Service is healthy',
        data={'status': 'ok'}
    ).to_dict(), 200

@health_bp.route('/status', methods=['GET'])
def status():
    """Get service status including Ollama connection."""
    ollama_status = 'disconnected'
    ollama_model = None

    try:
        response = requests.get(
            f"{OLLAMA_BASE_URL}/api/tags",
            timeout=5
        )
        if response.status_code == 200:
            ollama_status = 'connected'
            models = response.json().get('models', [])
            ollama_model = next((m['name'] for m in models if m['name'] == OLLAMA_MODEL), None)
    except Exception as e:
        logger.warning(f"Could not connect to Ollama at {OLLAMA_BASE_URL}: {e}")

    return SuccessResponse(
        data={
            'status': 'running',
            'agent': 'ready',
            'version': '0.1.0',
            'ollama': {
                'url': OLLAMA_BASE_URL,
                'status': ollama_status,
                'configured_model': OLLAMA_MODEL,
                'model_available': ollama_model is not None
            }
        }
    ).to_dict(), 200


@health_bp.route('/models', methods=['GET'])
def list_models():
    """List available models from the local runtime (Ollama)."""
    try:
        response = requests.get(
            f"{OLLAMA_BASE_URL}/api/tags",
            timeout=5,
        )
        response.raise_for_status()
        raw_models = response.json().get('models', [])
        names: list[str] = []
        for m in raw_models:
            clean = _sanitize_model_name(m.get('name', ''))
            if clean:
                names.append(clean)
        names.sort()
        return SuccessResponse(data={'models': names}).to_dict(), 200
    except requests.ConnectionError:
        logger.warning("Cannot reach Ollama at %s", OLLAMA_BASE_URL)
        return ErrorResponse(
            message='Unable to fetch models from local runtime',
            code='MODEL_LIST_UNAVAILABLE',
        ).to_dict(), 503
    except Exception as e:
        logger.error("Error fetching models: %s", e)
        return ErrorResponse(
            message='Unable to fetch models from local runtime',
            code='MODEL_LIST_UNAVAILABLE',
        ).to_dict(), 503
