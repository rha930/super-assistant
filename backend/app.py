from flask import Flask
from flask_cors import CORS
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Enable CORS
    CORS(app)
    
    # Register blueprints
    from routes.chat import chat_bp
    from routes.config import config_bp
    from routes.health import health_bp
    
    app.register_blueprint(chat_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(health_bp)
    
    @app.before_request
    def before_request():
        logger.info(f"Request: {request.method} {request.path}")
    
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal error: {error}")
        return {'error': 'Internal server error'}, 500
    
    return app

if __name__ == '__main__':
    from flask import request
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
