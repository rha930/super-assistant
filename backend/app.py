import logging
import secrets

from flask import Flask, request
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Enable CORS
    CORS(app)

    # --- Auth setup ---
    from config import (
        AUTH_ENABLED,
        AUTH_SECRET_KEY,
        AUTH_TOKEN_EXPIRY_HOURS,
        AUTH_USERS_FILE,
    )
    from middleware.auth import init_auth
    from routes.auth import auth_bp, init_auth_routes
    from services.auth_service import AuthService

    secret_key = AUTH_SECRET_KEY
    if not secret_key:
        secret_key = secrets.token_hex(32)
        logger.warning(
            "AUTH_SECRET_KEY not set — generated ephemeral key (will not persist across restarts)"
        )

    auth_service = AuthService(
        users_file=AUTH_USERS_FILE,
        secret_key=secret_key,
        token_expiry_hours=AUTH_TOKEN_EXPIRY_HOURS,
    )
    init_auth(auth_service, enabled=AUTH_ENABLED)
    init_auth_routes(auth_service)
    logger.info("Auth enabled=%s  users_file=%s", AUTH_ENABLED, AUTH_USERS_FILE)

    # Register blueprints
    from routes.chat import chat_bp
    from routes.config import config_bp
    from routes.gemini import gemini_bp
    from routes.health import health_bp
    from routes.notes import notes_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(gemini_bp)
    app.register_blueprint(notes_bp)

    @app.before_request
    def before_request():
        logger.info(f"Request: {request.method} {request.path}")

    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Not found"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal error: {error}")
        return {"error": "Internal server error"}, 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
