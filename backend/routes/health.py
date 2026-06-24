from flask import Blueprint
from models.response import SuccessResponse, ErrorResponse
import logging
import requests
from config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)
health_bp = Blueprint('health', __name__, url_prefix='/api')

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
