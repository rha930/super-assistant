import logging

from flask import Blueprint

from config import DB_CONNECTORS
from middleware.auth import require_auth
from models.response import ErrorResponse, SuccessResponse
from services.config_service import get_config_service
from services.database_service import DatabaseConnectorService

logger = logging.getLogger(__name__)
database_bp = Blueprint("database", __name__, url_prefix="/api/database")


@database_bp.route("/connectors", methods=["GET"])
@require_auth
def list_connectors():
    """List configured database connectors and their live status.

    Never includes connection URLs or credentials — only name, type, status.
    Returns an empty list when no connectors are configured.
    """
    try:
        db_cfg = get_config_service().get_config().get("database_connectors", {})
        service = DatabaseConnectorService(
            connector_defs=DB_CONNECTORS,
            timeout_seconds=int(db_cfg.get("timeout_seconds", 10)),
            max_rows=int(db_cfg.get("max_rows", 100)),
        )
        connectors = service.list_connectors()
        return SuccessResponse(data={"connectors": connectors}).to_dict(), 200
    except Exception as e:
        logger.error("Error listing database connectors: %s", e)
        return ErrorResponse(message="Failed to list database connectors").to_dict(), 500
