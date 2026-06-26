import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import jwt

logger = logging.getLogger(__name__)


class AuthService:
    """Simple file-backed authentication service with JWT tokens."""

    def __init__(self, users_file: str, secret_key: str, token_expiry_hours: int = 24):
        self.users_file = users_file
        self.secret_key = secret_key
        self.token_expiry_hours = token_expiry_hours
        self.users: list[dict] = []
        self._load_users()

    def _load_users(self) -> None:
        if not os.path.exists(self.users_file):
            logger.info("Users file not found at %s — starting with empty user list", self.users_file)
            self.users = []
            return
        try:
            with open(self.users_file, "r") as f:
                data = json.load(f)
            self.users = data.get("users", [])
            logger.info("Loaded %d user(s) from %s", len(self.users), self.users_file)
        except Exception as e:
            logger.error("Failed to load users file: %s", e)
            self.users = []

    def _save_users(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.users_file) or ".", exist_ok=True)
            with open(self.users_file, "w") as f:
                json.dump({"users": self.users}, f, indent=2)
        except Exception as e:
            logger.error("Failed to save users file: %s", e)

    def authenticate(self, username: str, password: str) -> Optional[dict]:
        """Verify credentials. Returns user dict (without hash) or None."""
        for user in self.users:
            if user.get("username") == username and user.get("active", True):
                stored_hash = user.get("password_hash", "")
                if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
                    return self._safe_user(user)
        return None

    def generate_token(self, user: dict) -> str:
        """Create a signed JWT with user_id, username, and exp claims."""
        payload = {
            "user_id": user["id"],
            "username": user["username"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=self.token_expiry_hours),
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def validate_token(self, token: str) -> Optional[dict]:
        """Decode and validate JWT. Returns payload or None if invalid/expired."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError:
            logger.debug("Invalid token")
            return None

    def create_user(self, username: str, password: str, display_name: str = "") -> dict:
        """Hash password, create user record, persist to file."""
        for user in self.users:
            if user.get("username") == username:
                raise ValueError(f"Username '{username}' already exists")

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
        user = {
            "id": f"user_{uuid.uuid4().hex[:12]}",
            "username": username,
            "password_hash": password_hash,
            "display_name": display_name or username,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
        }
        self.users.append(user)
        self._save_users()
        logger.info("Created user: %s", username)
        return self._safe_user(user)

    def list_users(self) -> list[dict]:
        """Return all users without password hashes."""
        return [self._safe_user(u) for u in self.users if u.get("active", True)]

    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        for user in self.users:
            if user.get("id") == user_id and user.get("active", True):
                return self._safe_user(user)
        return None

    @staticmethod
    def _safe_user(user: dict) -> dict:
        return {
            "id": user["id"],
            "username": user["username"],
            "display_name": user.get("display_name", user["username"]),
            "created_at": user.get("created_at"),
        }
