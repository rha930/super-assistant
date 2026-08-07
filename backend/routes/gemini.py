import logging

from config import GEMINI_API_KEY
from flask import Blueprint
from models.response import SuccessResponse
from services.config_service import get_config_service
from services.gemini_service import GeminiService

logger = logging.getLogger(__name__)
gemini_bp = Blueprint("gemini", __name__, url_prefix="/api/gemini")


@gemini_bp.route("/models", methods=["GET"])
def list_gemini_models():
    """List selectable Gemini models. Returns empty list if Gemini is disabled.

    The API key is read from the environment and never included in the response.
    """
    config = get_config_service().get_config()
    gemini = GeminiService(config.get("gemini", {}), api_key=GEMINI_API_KEY)
    available = gemini.is_available()
    models = gemini.available_models()
    return SuccessResponse(data={"models": models, "available": available}).to_dict(), 200
