import re
import logging

from flask import Blueprint, request
from models.response import SuccessResponse, ErrorResponse
from middleware.auth import require_auth

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# The AuthService instance is injected at import time from app.py.
_auth_service = None

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,30}$")
MIN_PASSWORD_LEN = 8


def init_auth_routes(auth_service):
    global _auth_service
    _auth_service = auth_service


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate and return a JWT."""
    try:
        data = request.get_json()
        if not data:
            return ErrorResponse(message="Missing request body").to_dict(), 400

        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))

        if not username or not password:
            return ErrorResponse(message="Username and password are required").to_dict(), 400

        user = _auth_service.authenticate(username, password)
        if not user:
            return ErrorResponse(message="Invalid username or password").to_dict(), 401

        token = _auth_service.generate_token(user)
        return SuccessResponse(
            message="Login successful",
            data={
                "token": token,
                "user": user,
                "expires_in": _auth_service.token_expiry_hours * 3600,
            },
        ).to_dict(), 200

    except Exception as e:
        logger.error("Error in login: %s", e)
        return ErrorResponse(message="An unexpected error occurred").to_dict(), 500


@auth_bp.route("/logout", methods=["POST"])
@require_auth
def logout():
    """Placeholder for server-side session revocation."""
    return SuccessResponse(message="Logged out").to_dict(), 200


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    """Return the currently authenticated user."""
    from flask import g

    user_id = g.current_user.get("user_id", "")
    user = _auth_service.get_user_by_id(user_id)
    if not user:
        return ErrorResponse(message="User not found").to_dict(), 404
    return SuccessResponse(data=user).to_dict(), 200


@auth_bp.route("/users", methods=["POST"])
@require_auth
def create_user():
    """Create a new user account."""
    try:
        data = request.get_json()
        if not data:
            return ErrorResponse(message="Missing request body").to_dict(), 400

        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        display_name = str(data.get("display_name", "")).strip()

        if not USERNAME_RE.match(username):
            return ErrorResponse(
                message="Username must be 3-30 alphanumeric/underscore characters"
            ).to_dict(), 400

        if len(password) < MIN_PASSWORD_LEN:
            return ErrorResponse(
                message=f"Password must be at least {MIN_PASSWORD_LEN} characters"
            ).to_dict(), 400

        user = _auth_service.create_user(username, password, display_name)
        return SuccessResponse(message="User created", data=user).to_dict(), 201

    except ValueError as e:
        return ErrorResponse(message=str(e)).to_dict(), 409
    except Exception as e:
        logger.error("Error creating user: %s", e)
        return ErrorResponse(message="An unexpected error occurred").to_dict(), 500
