import logging
import queue
import threading
import uuid
from collections.abc import Generator
from typing import Any

from config import GEMINI_API_KEY, GNEWS_API_KEY
from models.message import Message
from services.config_service import get_config_service
from services.gnews_service import GNewsService
from services.history_repository import ChatHistoryRepository
from services.history_repository_local import LocalChatHistoryRepository
from services.history_repository_redis import RedisChatHistoryRepository
from services.strands_provider import build_agent
from services.strands_tools import (
    build_describe_pins_tool,
    build_fly_to_location_tool,
    build_generate_graph_tool,
    build_news_search_tool,
    build_place_pin_tool,
)

logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling chat operations."""

    def __init__(self):
        self.conversations: dict[str, list] = {}
        self.current_conversation_id: str | None = None
        self.config_service = get_config_service()
        self.config: dict[str, Any] = self.config_service.get_config()
        history_cfg = self.config.get("history_config", {})
        self.history_repo: ChatHistoryRepository = self._build_history_repo(history_cfg)

    def _refresh_config(self) -> dict[str, Any]:
        """Reload the latest shared configuration for this request."""
        self.config = self.config_service.get_config()
        return self.config

    def _build_gnews_service(self) -> GNewsService:
        return GNewsService(self.config.get("gnews", {}), api_key=GNEWS_API_KEY)

    def _build_strands_agent(
        self,
        provider: str,
        history: list,
        artifact_store: list,
        callback_handler,
        widget_context_block: str | None = None,
    ):
        """Build a Strands Agent for this request with the configured provider and tools."""
        gnews = self._build_gnews_service()
        tools = [
            build_news_search_tool(gnews),
            build_generate_graph_tool(artifact_store),
            build_fly_to_location_tool(artifact_store),
            build_place_pin_tool(artifact_store),
            build_describe_pins_tool(),
        ]
        return build_agent(
            provider=provider,
            config=self.config,
            tools=tools,
            history=history,
            callback_handler=callback_handler,
            gemini_api_key=GEMINI_API_KEY,
            widget_context_block=widget_context_block,
        )

    @staticmethod
    def _zoom_label(zoom: int) -> str:
        if zoom <= 3:
            return "world/continent view"
        if zoom <= 6:
            return "country/region view"
        if zoom <= 9:
            return "city-area view"
        if zoom <= 12:
            return "neighbourhood view"
        return "street-level view"

    @staticmethod
    def _build_widget_context_block(ctx: dict | None) -> str | None:
        """Convert a widget_context dict into a natural-language system prompt block."""
        if not ctx or not isinstance(ctx, dict):
            return None
        panel = ctx.get("active_panel")
        if not panel:
            return None
        lines = ["User's current workspace context:", f"- Active widget: {str(panel).title()}"]
        if panel == "map" and isinstance(ctx.get("map"), dict):
            m = ctx["map"]
            try:
                zoom = int(m.get("zoom", 0))
            except (TypeError, ValueError):
                zoom = 0
            label = ChatService._zoom_label(zoom)
            lines.append(f"- Map zoom level: {zoom} ({label})")
            try:
                lat = float(m["center_lat"])
                lng = float(m["center_lng"])
                lines.append(f"- Map center: approximately ({lat:.4f}, {lng:.4f})")
            except (KeyError, TypeError, ValueError):
                pass
            count = m.get("point_count", 0)
            lines.append(f"- User has placed {count} map pin(s)")
            pins_json = m.get("pins_json", "")
            if pins_json and isinstance(pins_json, str) and pins_json != "[]":
                lines.append(f"- Pin data (label, lat, lng): {pins_json[:500]}")
        elif panel == "graph" and isinstance(ctx.get("graph"), dict):
            g = ctx["graph"]
            lines.append(f"- Graphs displayed: {g.get('chart_count', 0)}")
            if g.get("active_chart_type"):
                lines.append(f"- Primary chart type: {g['active_chart_type']}")
            if g.get("active_chart_title"):
                lines.append(f"- Primary chart title: {str(g['active_chart_title'])[:200]}")
        elif panel == "notes" and isinstance(ctx.get("notes"), dict):
            n = ctx["notes"]
            if n.get("note_title"):
                lines.append(f'- Active note: "{str(n["note_title"])[:200]}"')
            if n.get("note_taking_mode"):
                lines.append("- Note-taking mode is active: agent responses are being saved to this note.")
        return "\n".join(lines)

    @staticmethod
    def _extract_text_from_result(result) -> str:
        """Extract plain text from a Strands AgentResult."""
        try:
            message = result.message or {}
            content = message.get("content", [])
            return "".join(block.get("text", "") for block in content if "text" in block)
        except Exception:
            return str(result)

    def _build_history_repo(self, history_cfg: dict[str, Any]) -> ChatHistoryRepository:
        backend_type = str(history_cfg.get("backend_type", "local")).strip().lower()
        max_messages = int(history_cfg.get("max_messages_per_conversation", 200))

        if backend_type == "redis":
            redis_url = str(history_cfg.get("redis_url", "redis://localhost:6379/0")).strip()
            redis_prefix = str(history_cfg.get("redis_prefix", "chat")).strip() or "chat"
            try:
                logger.info("Using Redis chat history backend")
                return RedisChatHistoryRepository(
                    redis_url=redis_url,
                    redis_prefix=redis_prefix,
                    max_messages_per_conversation=max_messages,
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize Redis history backend, falling back to local: %s",
                    e,
                )

        logger.info("Using local SQLite chat history backend")
        return LocalChatHistoryRepository(
            db_path=history_cfg.get("db_path", "./backend/data/chat_history.db"),
            max_messages_per_conversation=max_messages,
        )

    def process_message(
        self,
        message: str,
        conversation_id: str | None = None,
        user_id: str = "anonymous",
        widget_context: dict | None = None,
    ) -> dict[str, Any]:
        """Process a user message and return the agent's full response."""
        try:
            self._refresh_config()

            if not conversation_id:
                conversation_id = f"conv_{uuid.uuid4().hex}"

            user_msg = Message(role="user", content=message)
            self.history_repo.append_message(
                user_id=user_id,
                conversation_id=conversation_id,
                role="user",
                content=message,
                metadata=user_msg.metadata,
            )

            history = self._build_context_history(user_id, conversation_id)
            context_cfg = self.config.get("context_config", {})
            provider = (self.config.get("provider") or "ollama").strip().lower()

            artifact_store: list = []
            tool_calls_collected: list = []

            def _cb(**event: Any) -> None:
                if "current_tool_use" in event:
                    tuse = event.get("current_tool_use") or {}
                    name = tuse.get("name") if isinstance(tuse, dict) else None
                    if name:
                        tool_calls_collected.append({"name": name, "status": "success"})

            agent = self._build_strands_agent(
                provider, history, artifact_store, _cb,
                widget_context_block=self._build_widget_context_block(widget_context),
            )
            sdk_result = agent(message)

            agent_response = self._extract_text_from_result(sdk_result)
            artifacts = list(artifact_store)

            logger.info(
                "Strands agent completed (sync): conversation_id=%s artifacts=%s tools=%s",
                conversation_id,
                len(artifacts),
                len(tool_calls_collected),
            )

            context_meta = {
                "history_message_count": len(history),
                "context_max_messages": context_cfg.get("max_messages", 12),
                "context_max_input_chars": context_cfg.get("max_input_chars", 12000),
            }
            agent_metadata = {
                "provider": provider,
                "model": self.config.get("model"),
                "tool_calls": tool_calls_collected,
                "artifacts": artifacts,
                "context": context_meta,
            }

            agent_msg = Message(role="agent", content=agent_response, metadata=agent_metadata)
            self.history_repo.append_message(
                user_id=user_id,
                conversation_id=conversation_id,
                role="agent",
                content=agent_response,
                metadata=agent_msg.metadata,
            )

            self.current_conversation_id = conversation_id

            return {
                "response": agent_response,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "metadata": agent_msg.metadata,
                "artifacts": artifacts,
            }

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            raise

    def start_conversation(
        self,
        message: str,
        conversation_id: str | None = None,
        user_id: str = "anonymous",
    ) -> str:
        """Ensure conversation exists and append the user message."""
        if not conversation_id:
            conversation_id = f"conv_{uuid.uuid4().hex}"

        user_msg = Message(role="user", content=message)
        self.history_repo.append_message(
            user_id=user_id,
            conversation_id=conversation_id,
            role="user",
            content=message,
            metadata=user_msg.metadata,
        )
        self.current_conversation_id = conversation_id
        return conversation_id

    def stream_message(
        self,
        message: str,
        conversation_id: str | None = None,
        user_id: str = "anonymous",
        widget_context: dict | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Yield SSE-compatible response chunks from the Strands agent."""
        try:
            self._refresh_config()
            cid = self.start_conversation(message, conversation_id, user_id)
            history = self._build_context_history(user_id, cid)
            context_cfg = self.config.get("context_config", {})
            provider = (self.config.get("provider") or "ollama").strip().lower()

            artifact_store: list = []
            tool_calls_tracking: list = []
            event_queue: queue.Queue = queue.Queue()

            def _cb(**event: Any) -> None:
                if "data" in event and event["data"]:
                    event_queue.put(
                        {
                            "chunk": event["data"],
                            "done": False,
                            "tool_calls": list(tool_calls_tracking),
                        }
                    )
                elif "current_tool_use" in event:
                    tuse = event.get("current_tool_use") or {}
                    name = tuse.get("name") if isinstance(tuse, dict) else None
                    if name:
                        tool_calls_tracking.append({"name": name, "status": "in_progress"})
                        event_queue.put(
                            {
                                "chunk": "",
                                "done": False,
                                "thinking": f"Using {name}...",
                                "tool_calls": list(tool_calls_tracking),
                            }
                        )
                elif "result" in event:
                    for tc in tool_calls_tracking:
                        tc["status"] = "success"
                    event_queue.put(
                        {
                            "chunk": "",
                            "done": True,
                            "tool_calls": list(tool_calls_tracking),
                            "artifacts": list(artifact_store),
                            "provider": provider,
                            "model": self.config.get("model"),
                        }
                    )

            agent = self._build_strands_agent(
                provider, history, artifact_store, _cb,
                widget_context_block=self._build_widget_context_block(widget_context),
            )

            def _run_agent() -> None:
                try:
                    agent(message)
                except Exception as exc:
                    logger.error("Strands agent error in stream: %s", exc)
                    event_queue.put({"error": str(exc), "done": True})
                finally:
                    event_queue.put(None)  # sentinel

            threading.Thread(target=_run_agent, daemon=True).start()

            context_meta = {
                "history_message_count": len(history),
                "context_max_messages": context_cfg.get("max_messages", 12),
                "context_max_input_chars": context_cfg.get("max_input_chars", 12000),
            }

            while True:
                item = event_queue.get()
                if item is None:
                    break
                if "error" in item:
                    raise RuntimeError(item["error"])

                done = item.get("done", False)
                yield {
                    "conversation_id": cid,
                    "chunk": item.get("chunk", ""),
                    "done": done,
                    "metadata": {
                        "tool_calls": item.get("tool_calls", []),
                        "artifacts": item.get("artifacts", []),
                        "provider": item.get("provider", provider),
                        "model": item.get("model", self.config.get("model")),
                        "context": context_meta,
                    },
                    **({"thinking": item["thinking"]} if "thinking" in item else {}),
                }

        except Exception as e:
            logger.error(f"Error streaming message: {e}")
            raise

    def finalize_stream_message(
        self,
        conversation_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        user_id: str = "anonymous",
    ):
        """Persist the completed streamed assistant message to history."""
        # Artifacts were collected by generate_graph tool during the stream
        artifacts = (metadata or {}).get("artifacts", [])

        agent_msg = Message(
            role="agent",
            content=content,
            metadata={**(metadata or {"tool_calls": []}), "artifacts": artifacts},
        )
        self.history_repo.append_message(
            user_id=user_id,
            conversation_id=conversation_id,
            role="agent",
            content=content,
            metadata=agent_msg.metadata,
        )
        return artifacts

    def get_history(self, conversation_id: str, user_id: str = "anonymous") -> list:
        """Get conversation history."""
        return self.history_repo.get_messages(user_id, conversation_id)

    def list_conversations(self, user_id: str = "anonymous", limit: int = 50) -> list:
        """List conversations for a user ordered by most recent activity."""
        return self.history_repo.list_conversations(user_id, limit=limit)

    def _build_context_history(self, user_id: str, conversation_id: str) -> list:
        """Build bounded conversation history for agent context, excluding newest user turn."""
        messages = self.history_repo.get_messages(user_id, conversation_id)
        if not messages:
            return []

        # Exclude latest user turn because it is passed separately as user_message.
        trimmed = messages[:-1] if len(messages) > 0 else []
        return trimmed

    def reset(self, user_id: str = "anonymous"):
        """Reset the current conversation."""
        if self.current_conversation_id:
            self.history_repo.delete_conversation(user_id, self.current_conversation_id)
            self.current_conversation_id = None
