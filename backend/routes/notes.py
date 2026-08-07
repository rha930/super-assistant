import logging

from flask import Blueprint, g, request

from middleware.auth import require_auth
from models.response import ErrorResponse, SuccessResponse
from services.note_service import NoteService

logger = logging.getLogger(__name__)

notes_bp = Blueprint("notes", __name__, url_prefix="/api/notes")
note_service = NoteService()


def _get_user_id() -> str:
    return g.current_user.get("user_id", "anonymous")


# ------------------------------------------------------------------
# CRUD
# ------------------------------------------------------------------


@notes_bp.route("", methods=["POST"])
@require_auth
def create_note():
    data = request.get_json() or {}
    title = (data.get("title") or "Untitled Note").strip()[:200]
    content = (data.get("content") or "")[:100_000]
    try:
        note = note_service.create_note(_get_user_id(), title, content)
        return SuccessResponse(data={"note": note}, message="Note created").to_dict(), 201
    except Exception as e:
        logger.error("Error creating note: %s", e)
        return ErrorResponse(message=str(e)).to_dict(), 500


@notes_bp.route("", methods=["GET"])
@require_auth
def list_notes():
    limit = request.args.get("limit", 50, type=int)
    try:
        notes = note_service.list_notes(_get_user_id(), limit=limit)
        return SuccessResponse(data={"notes": notes}).to_dict(), 200
    except Exception as e:
        logger.error("Error listing notes: %s", e)
        return ErrorResponse(message=str(e)).to_dict(), 500


@notes_bp.route("/<note_id>", methods=["GET"])
@require_auth
def get_note(note_id: str):
    note = note_service.get_note(_get_user_id(), note_id)
    if note is None:
        return ErrorResponse(message="Note not found").to_dict(), 404
    return SuccessResponse(data={"note": note}).to_dict(), 200


@notes_bp.route("/<note_id>", methods=["PUT"])
@require_auth
def update_note(note_id: str):
    data = request.get_json() or {}
    title = data.get("title")
    content = data.get("content")
    if title is not None:
        title = title.strip()[:200]
    if content is not None:
        content = content[:100_000]
    try:
        note = note_service.update_note(_get_user_id(), note_id, title=title, content=content)
        if note is None:
            return ErrorResponse(message="Note not found").to_dict(), 404
        return SuccessResponse(data={"note": note}, message="Note updated").to_dict(), 200
    except Exception as e:
        logger.error("Error updating note: %s", e)
        return ErrorResponse(message=str(e)).to_dict(), 500


@notes_bp.route("/<note_id>/append", methods=["PATCH"])
@require_auth
def append_note(note_id: str):
    data = request.get_json() or {}
    content = data.get("content", "")
    if not content:
        return ErrorResponse(message="Missing content").to_dict(), 400
    try:
        note = note_service.note_repo.append_content(_get_user_id(), note_id, content[:100_000])
        if note is None:
            return ErrorResponse(message="Note not found").to_dict(), 404
        return SuccessResponse(data={"note": note}, message="Content appended").to_dict(), 200
    except Exception as e:
        logger.error("Error appending to note: %s", e)
        return ErrorResponse(message=str(e)).to_dict(), 500


@notes_bp.route("/<note_id>", methods=["DELETE"])
@require_auth
def delete_note(note_id: str):
    deleted = note_service.delete_note(_get_user_id(), note_id)
    if not deleted:
        return ErrorResponse(message="Note not found").to_dict(), 404
    return SuccessResponse(message="Note deleted").to_dict(), 200


# ------------------------------------------------------------------
# LLM expansion
# ------------------------------------------------------------------


@notes_bp.route("/expand", methods=["POST"])
@require_auth
def expand_input():
    data = request.get_json() or {}
    user_input = (data.get("input") or "").strip()
    if not user_input:
        return ErrorResponse(message="Missing input").to_dict(), 400

    existing_content = data.get("existing_content") or ""
    try:
        result = note_service.expand_note_content(user_input, existing_content)
        return SuccessResponse(data=result).to_dict(), 200
    except Exception as e:
        logger.error("Error expanding note content: %s", e)
        return ErrorResponse(message=str(e)).to_dict(), 500


@notes_bp.route("/expand-more", methods=["POST"])
@require_auth
def expand_more():
    data = request.get_json() or {}
    previous = (data.get("previous_suggestion") or "").strip()
    if not previous:
        return ErrorResponse(message="Missing previous_suggestion").to_dict(), 400

    existing_content = data.get("existing_content") or ""
    try:
        result = note_service.expand_more(previous, existing_content)
        return SuccessResponse(data=result).to_dict(), 200
    except Exception as e:
        logger.error("Error expanding more: %s", e)
        return ErrorResponse(message=str(e)).to_dict(), 500
