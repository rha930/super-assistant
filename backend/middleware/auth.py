import functools
import logging

from flask import g, jsonify, request

logger = logging.getLogger(__name__)

# The AuthService instance is set at app startup via init_auth().
_auth_service = None
_auth_enabled = True


def init_auth(auth_service, enabled: bool = True):
    """Called once during app creation to wire the auth service."""
    global _auth_service, _auth_enabled
    _auth_service = auth_service
    _auth_enabled = enabled


def require_auth(f):
    """Decorator that validates JWT from the Authorization header.

    On success, sets ``flask.g.current_user`` with the decoded token payload
    (including ``user_id`` and ``username``).
    Returns 401 on missing / invalid / expired token.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not _auth_enabled:
            # Auth disabled — fall back to anonymous identity.
            g.current_user = {"user_id": "anonymous", "username": "anonymous"}
            return f(*args, **kwargs)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"success": False, "message": "Authentication required"}), 401

        token = auth_header[7:]
        if not _auth_service:
            logger.error("Auth service not initialized")
            return jsonify({"success": False, "message": "Server auth misconfigured"}), 500

        payload = _auth_service.validate_token(token)
        if payload is None:
            return jsonify({"success": False, "message": "Invalid or expired token"}), 401

        g.current_user = payload
        return f(*args, **kwargs)

    return wrapper
