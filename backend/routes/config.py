from flask import Blueprint, request, jsonify
from services.config_service import ConfigService
from models.response import SuccessResponse, ErrorResponse
import logging

logger = logging.getLogger(__name__)
config_bp = Blueprint('config', __name__, url_prefix='/api/config')
config_service = ConfigService()

@config_bp.route('', methods=['GET'])
def get_config():
    """Get current configuration."""
    try:
        config = config_service.get_config()
        return SuccessResponse(data=config).to_dict(), 200
    except Exception as e:
        logger.error(f"Error in get_config: {e}")
        return ErrorResponse(message=str(e)).to_dict(), 500

@config_bp.route('', methods=['POST'])
def update_config():
    """Update configuration."""
    try:
        data = request.get_json()
        
        if not data:
            return ErrorResponse(message='Missing configuration data').to_dict(), 400
        
        updated_config = config_service.update_config(data)
        return SuccessResponse(data=updated_config, message='Configuration updated').to_dict(), 200
    
    except Exception as e:
        logger.error(f"Error in update_config: {e}")
        return ErrorResponse(message=str(e)).to_dict(), 500

@config_bp.route('/reset', methods=['POST'])
def reset_config():
    """Reset configuration to defaults."""
    try:
        config = config_service.reset_config()
        return SuccessResponse(data=config, message='Configuration reset to defaults').to_dict(), 200
    except Exception as e:
        logger.error(f"Error in reset_config: {e}")
        return ErrorResponse(message=str(e)).to_dict(), 500
