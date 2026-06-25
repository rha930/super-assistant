from flask import Blueprint, request, Response, stream_with_context
from services.chat_service import ChatService
import json
from models.response import SuccessResponse, ErrorResponse
import logging

logger = logging.getLogger(__name__)
chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')
chat_service = ChatService()


def _resolve_user_id(data=None):
    """Resolve user identity from header first, then body, with safe fallback."""
    header_user = request.headers.get('X-User-Id', '').strip()
    if header_user:
        return header_user
    if data and isinstance(data, dict):
        body_user = str(data.get('user_id', '')).strip()
        if body_user:
            return body_user
    return 'anonymous'

@chat_bp.route('/message', methods=['POST'])
def send_message():
    """
    Send a message to the Strands agent.
    
    Expected JSON:
    {
        "message": "user message",
        "conversation_id": "optional_conversation_id"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return ErrorResponse(message='Missing required field: message').to_dict(), 400
        
        message = data['message']
        conversation_id = data.get('conversation_id')
        user_id = _resolve_user_id(data)
        
        try:
            response = chat_service.process_message(message, conversation_id, user_id=user_id)
            return SuccessResponse(data=response).to_dict(), 200
        except RuntimeError as e:
            # Connection errors from Ollama
            error_msg = str(e)
            logger.error(f"Runtime error: {error_msg}")
            return ErrorResponse(
                message=error_msg,
                code='OLLAMA_ERROR'
            ).to_dict(), 503
        except Exception as e:
            logger.error(f"Error in send_message: {e}")
            return ErrorResponse(message=str(e)).to_dict(), 500
    
    except Exception as e:
        logger.error(f"Unexpected error in send_message: {e}")
        return ErrorResponse(message='An unexpected error occurred').to_dict(), 500

@chat_bp.route('/stream', methods=['POST'])
def stream_message():
    """Stream a message response from the agent using Server-Sent Events (SSE)."""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return ErrorResponse(message='Missing required field: message').to_dict(), 400

        message = data['message']
        conversation_id = data.get('conversation_id')
        user_id = _resolve_user_id(data)

        @stream_with_context
        def event_stream():
            full_response = ''
            cid = conversation_id
            final_metadata = {'tool_calls': []}
            chunk_count = 0

            # Initial status update so UI can show immediate activity.
            init_payload = {
                'conversation_id': cid,
                'chunk': '',
                'done': False,
                'thinking': 'Reviewing your request...'
            }
            yield f"data: {json.dumps(init_payload)}\n\n"

            try:
                for event in chat_service.stream_message(message, conversation_id, user_id=user_id):
                    cid = event.get('conversation_id', cid)
                    chunk = event.get('chunk', '')
                    done = event.get('done', False)
                    metadata = event.get('metadata', {'tool_calls': []})
                    chunk_count += 1

                    if done:
                        thinking = 'Finalizing response...'
                    elif chunk_count < 5:
                        thinking = 'Analyzing context...'
                    elif chunk_count < 15:
                        thinking = 'Drafting response...'
                    else:
                        thinking = 'Refining details...'

                    if chunk:
                        full_response += chunk

                    if done:
                        final_metadata = metadata
                        break

                    payload = {
                        'conversation_id': cid,
                        'chunk': chunk,
                        'done': False,
                        'metadata': metadata,
                        'thinking': thinking
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

                if cid:
                    artifacts = chat_service.finalize_stream_message(
                        conversation_id=cid,
                        content=full_response,
                        metadata=final_metadata,
                        user_id=user_id
                    )

                    # Emit a deterministic final done event carrying artifacts for the Graph Panel.
                    final_payload = {
                        'conversation_id': cid,
                        'chunk': '',
                        'done': True,
                        'metadata': {
                            **(final_metadata or {}),
                            'artifacts': artifacts
                        },
                        'artifacts': artifacts,
                        'thinking': 'Done.'
                    }
                    yield f"data: {json.dumps(final_payload)}\n\n"
            except Exception as e:
                logger.error(f"Error in stream endpoint: {e}")
                err_payload = {
                    'error': str(e),
                    'done': True,
                    'thinking': 'Stopped due to an error.'
                }
                yield f"data: {json.dumps(err_payload)}\n\n"

        return Response(
            event_stream(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        logger.error(f"Unexpected error in stream_message: {e}")
        return ErrorResponse(message='An unexpected error occurred').to_dict(), 500

@chat_bp.route('/history/<conversation_id>', methods=['GET'])
def get_history(conversation_id):
    """Get conversation history."""
    try:
        user_id = _resolve_user_id(None)
        history = chat_service.get_history(conversation_id, user_id=user_id)
        return SuccessResponse(data={'messages': history}).to_dict(), 200
    except Exception as e:
        logger.error(f"Error in get_history: {e}")
        return ErrorResponse(message=str(e)).to_dict(), 500


@chat_bp.route('/conversations', methods=['GET'])
def list_conversations():
    """List user conversations ordered by latest activity."""
    try:
        user_id = _resolve_user_id(None)
        limit_raw = request.args.get('limit', '50')
        try:
            limit = max(1, min(200, int(limit_raw)))
        except ValueError:
            limit = 50

        conversations = chat_service.list_conversations(user_id=user_id, limit=limit)
        return SuccessResponse(data={'conversations': conversations}).to_dict(), 200
    except Exception as e:
        logger.error(f"Error in list_conversations: {e}")
        return ErrorResponse(message=str(e)).to_dict(), 500

@chat_bp.route('/reset', methods=['DELETE'])
def reset_conversation():
    """Reset/clear the current conversation."""
    try:
        user_id = _resolve_user_id(None)
        chat_service.reset(user_id=user_id)
        return SuccessResponse(message='Conversation reset').to_dict(), 200
    except Exception as e:
        logger.error(f"Error in reset_conversation: {e}")
        return ErrorResponse(message=str(e)).to_dict(), 500
