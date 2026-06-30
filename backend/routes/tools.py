from flask import Blueprint
from models.response import SuccessResponse
from services.web_search_service import WebSearchService
import logging

logger = logging.getLogger(__name__)
tools_bp = Blueprint('tools', __name__, url_prefix='/api/tools')

_web_search_service = WebSearchService()


@tools_bp.route('/web-search/status', methods=['GET'])
def web_search_status():
    """Return whether the web search tool is enabled and available."""
    from config import WEB_SEARCH_ENABLED

    return SuccessResponse(data={
        'enabled': WEB_SEARCH_ENABLED,
        'provider': 'duckduckgo',
        'available': _web_search_service.is_available(),
    }).to_dict(), 200
