import logging
import uuid
from typing import Any

from config import GEMINI_API_KEY
from models.message import Message

from services.config_service import get_config_service
from services.gemini_service import GeminiService
from services.graph_artifact_service import GraphArtifactService
from services.history_repository import ChatHistoryRepository
from services.history_repository_local import LocalChatHistoryRepository
from services.history_repository_redis import RedisChatHistoryRepository
from services.strands_agent import StrandsAgentService

logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling chat operations."""

    def __init__(self):
        self.conversations: dict[str, list] = {}
        self.current_conversation_id: str | None = None
        self.agent = StrandsAgentService()
        self.graph_artifact_service = GraphArtifactService()
        self.config_service = get_config_service()
        self.config: dict[str, Any] = self.config_service.get_config()
        history_cfg = self.config.get("history_config", {})
        self.history_repo: ChatHistoryRepository = self._build_history_repo(history_cfg)

    def _refresh_config(self) -> dict[str, Any]:
        """Reload the latest shared configuration for this request."""
        self.config = self.config_service.get_config()
        return self.config

    def _build_gemini_service(self) -> GeminiService:
        """Construct a GeminiService from the current config + env API key."""
        return GeminiService(self.config.get("gemini", {}), api_key=GEMINI_API_KEY)

    def _invoke_ollama(
        self, message: str, history: list, context_cfg: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke the local Ollama agent and normalize the result metadata."""
        params = self.config.get("model_parameters", {})
        result = self.agent.invoke_agent(
            agent_id=None,
            session_id=self.current_conversation_id,
            user_message=message,
            system_prompt=self.config.get("system_prompt"),
            conversation_history=history,
            model=self.config.get("model"),
            temperature=params.get("temperature", 0.7),
            top_p=params.get("top_p", 0.9),
            max_tokens=params.get("max_tokens", 1000),
            context_max_messages=context_cfg.get("max_messages", 12),
            context_max_input_chars=context_cfg.get("max_input_chars", 12000),
        )
        metadata = result.get("metadata", {}) or {}
        metadata.setdefault("provider", "ollama")
        metadata.setdefault("model", self.config.get("model"))
        result["metadata"] = metadata
        return result

    def _ollama_stream(
        self,
        message: str,
        history: list,
        context_cfg: dict[str, Any],
        fallback: bool = False,
    ):
        """Yield Ollama stream events, tagging provider (and fallback) metadata."""
        params = self.config.get("model_parameters", {})
        model = self.config.get("model")
        for event in self.agent.stream_agent(
            user_message=message,
            system_prompt=self.config.get("system_prompt"),
            conversation_history=history,
            model=model,
            temperature=params.get("temperature", 0.7),
            top_p=params.get("top_p", 0.9),
            max_tokens=params.get("max_tokens", 1000),
            context_max_messages=context_cfg.get("max_messages", 12),
            context_max_input_chars=context_cfg.get("max_input_chars", 12000),
        ):
            metadata = event.get("metadata", {}) or {}
            metadata.setdefault("provider", "ollama")
            metadata.setdefault("model", model)
            if fallback:
                metadata["fallback_from"] = "gemini"
            event["metadata"] = metadata
            yield event

    def _build_history_repo(self, history_cfg: dict[str, Any]) -> ChatHistoryRepository:
        backend_type = str(history_cfg.get("backend_type", "local")).strip().lower()
        max_messages = int(history_cfg.get("max_messages_per_conversation", 200))

        if backend_type == "redis":
            redis_url = str(
                history_cfg.get("redis_url", "redis://localhost:6379/0")
            ).strip()
            redis_prefix = (
                str(history_cfg.get("redis_prefix", "chat")).strip() or "chat"
            )
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
    ) -> dict[str, Any]:
        """
        Process a user message and get a response from the Strands agent.

        Args:
            message: User message
            conversation_id: Optional conversation ID

        Returns:
            Dictionary with agent response and metadata
        """
        try:
            self._refresh_config()

            # Use existing or create new conversation ID
            if not conversation_id:
                conversation_id = f"conv_{uuid.uuid4().hex}"

            # Store user message
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
            gemini = self._build_gemini_service()
            params = self.config.get("model_parameters", {})

            if provider == "gemini" and gemini.is_available():
                logger.info(
                    "Routing generation to Gemini (model=%s)",
                    self.config.get("model"),
                )
                try:
                    result = gemini.generate(
                        user_message=message,
                        system_prompt=self.config.get("system_prompt"),
                        conversation_history=history,
                        model=self.config.get("model"),
                        temperature=params.get("temperature", 0.7),
                        top_p=params.get("top_p", 0.9),
                        max_tokens=params.get("max_tokens", 1000),
                    )
                    agent_response = result.get("content", "")
                    agent_result = {
                        "response": agent_response,
                        "metadata": {
                            "provider": "gemini",
                            "model": result.get("model"),
                            "tool_calls": [],
                            "usage": result.get("usage"),
                        },
                    }
                except Exception as gemini_err:
                    logger.error(
                        "Gemini generation failed, falling back to Ollama: %s",
                        gemini_err,
                    )
                    try:
                        agent_result = self._invoke_ollama(
                            message, history, context_cfg
                        )
                        agent_result["metadata"]["fallback_from"] = "gemini"
                    except Exception:
                        logger.error(
                            "Ollama fallback also failed; re-raising original Gemini error"
                        )
                        raise RuntimeError(
                            f"Gemini error: {gemini_err}"
                        ) from gemini_err
            else:
                if provider == "gemini":
                    logger.warning(
                        "Provider is 'gemini' but it is unavailable (enabled/API key missing); using Ollama"
                    )
                agent_result = self._invoke_ollama(message, history, context_cfg)

            agent_response = agent_result.get("response", "")
            agent_tool_calls = agent_result.get("metadata", {}).get("tool_calls", [])

            # Only generate graph artifacts if user message indicates visualization intent
            artifacts = []
            if self.agent._wants_visualization(message):
                artifacts = self.graph_artifact_service.create_graph_artifacts(
                    message, agent_response
                )

            logger.info(
                "Graph artifacts generated (sync): conversation_id=%s count=%s intent=%s",
                conversation_id,
                len(artifacts),
                self.agent._wants_visualization(message),
            )
            context_meta = {
                "history_message_count": len(history),
                "context_max_messages": context_cfg.get("max_messages", 12),
                "context_max_input_chars": context_cfg.get("max_input_chars", 12000),
            }

            agent_msg = Message(
                role="agent",
                content=agent_response,
                metadata={
                    **agent_result.get(
                        "metadata", {"tokens_used": 0, "tool_calls": []}
                    ),
                    "tool_calls": agent_tool_calls,
                    "artifacts": artifacts,
                    "context": context_meta,
                },
            )
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
    ):
        """Yield response chunks from the model and keep conversation state."""
        try:
            self._refresh_config()
            cid = self.start_conversation(message, conversation_id, user_id)
            history = self._build_context_history(user_id, cid)
            context_cfg = self.config.get("context_config", {})
            params = self.config.get("model_parameters", {})

            provider = (self.config.get("provider") or "ollama").strip().lower()
            gemini = self._build_gemini_service()

            if provider == "gemini" and gemini.is_available():
                logger.info(
                    "Routing streaming generation to Gemini (model=%s)",
                    self.config.get("model"),
                )
                try:
                    stream = gemini.stream_generate(
                        user_message=message,
                        system_prompt=self.config.get("system_prompt"),
                        conversation_history=history,
                        model=self.config.get("model"),
                        temperature=params.get("temperature", 0.7),
                        top_p=params.get("top_p", 0.9),
                        max_tokens=params.get("max_tokens", 1000),
                    )
                    # Materialize so a failure surfaces before we start yielding.
                    stream = list(stream)
                except Exception as gemini_err:
                    logger.error(
                        "Gemini stream failed, falling back to Ollama: %s", gemini_err
                    )
                    try:
                        stream = list(
                            self._ollama_stream(
                                message, history, context_cfg, fallback=True
                            )
                        )
                    except Exception:
                        logger.error(
                            "Ollama fallback also failed; re-raising original Gemini error"
                        )
                        raise RuntimeError(
                            f"Gemini error: {gemini_err}"
                        ) from gemini_err
            else:
                if provider == "gemini":
                    logger.warning(
                        "Provider is 'gemini' but it is unavailable (enabled/API key missing); using Ollama"
                    )
                stream = self._ollama_stream(message, history, context_cfg)

            for event in stream:
                metadata = event.get("metadata", {"tool_calls": []})
                done = event.get("done", False)

                if done:
                    metadata = {
                        **metadata,
                        "tool_calls": metadata.get("tool_calls", []),
                        "artifacts": [],
                    }

                yield {
                    "conversation_id": cid,
                    "chunk": event.get("chunk", ""),
                    "done": done,
                    "metadata": {
                        **metadata,
                        "context": {
                            "history_message_count": len(history),
                            "context_max_messages": context_cfg.get("max_messages", 12),
                            "context_max_input_chars": context_cfg.get(
                                "max_input_chars", 12000
                            ),
                        },
                    },
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
        """Persist final streamed assistant message to history."""
        conversation_messages = self.history_repo.get_messages(user_id, conversation_id)
        user_prompt = ""
        if conversation_messages:
            for msg in reversed(conversation_messages):
                if msg.get("role") == "user":
                    user_prompt = msg.get("content", "")
                    break

        # Only generate graph artifacts if user message indicates visualization intent
        artifacts = []
        if self.agent._wants_visualization(user_prompt):
            artifacts = self.graph_artifact_service.create_graph_artifacts(
                user_prompt, content
            )

        logger.info(
            "Graph artifacts generated (stream): conversation_id=%s count=%s intent=%s",
            conversation_id,
            len(artifacts),
            self.agent._wants_visualization(user_prompt),
        )

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
