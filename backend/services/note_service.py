import logging
from typing import Any

from config import GEMINI_API_KEY, NOTE_EXPANSION_SYSTEM_PROMPT

from services.config_service import get_config_service
from services.gemini_service import GeminiService
from services.note_repository import NoteRepository
from services.strands_agent import StrandsAgentService

logger = logging.getLogger(__name__)

# Maximum characters of existing note content to include as LLM context.
_MAX_NOTE_CONTEXT_CHARS = 4000


class NoteService:
    """Orchestrates LLM expansion and note management."""

    def __init__(self) -> None:
        from config import HISTORY_DB_PATH

        self.note_repo = NoteRepository(db_path=HISTORY_DB_PATH)
        self.config_service = get_config_service()
        self.agent = StrandsAgentService()

    def _generate(self, prompt: str, system_prompt: str) -> str:
        """Route a generation request to the active LLM provider and return text."""
        config = self.config_service.get_config()
        provider = (config.get("provider") or "ollama").strip().lower()
        params = config.get("model_parameters", {})

        if provider == "gemini":
            gemini = GeminiService(config.get("gemini", {}), api_key=GEMINI_API_KEY)
            if gemini.is_available():
                result = gemini.generate(
                    user_message=prompt,
                    system_prompt=system_prompt,
                    model=config.get("model"),
                    temperature=params.get("temperature", 0.7),
                    max_tokens=params.get("max_tokens", 1000),
                )
                return result.get("content", "")

        # Ollama (default / fallback)
        result = self.agent.invoke_agent(
            agent_id=None,
            session_id=None,
            user_message=prompt,
            system_prompt=system_prompt,
            model=config.get("model"),
            temperature=params.get("temperature", 0.7),
            max_tokens=params.get("max_tokens", 1000),
        )
        return result.get("response", "")

    # ------------------------------------------------------------------
    # CRUD delegates
    # ------------------------------------------------------------------
    def create_note(
        self, user_id: str, title: str = "Untitled Note", content: str = ""
    ) -> dict[str, Any]:
        return self.note_repo.create_note(user_id, title, content)

    def get_note(self, user_id: str, note_id: str) -> dict[str, Any] | None:
        return self.note_repo.get_note(user_id, note_id)

    def update_note(
        self, user_id: str, note_id: str, **kwargs: Any
    ) -> dict[str, Any] | None:
        return self.note_repo.update_note(user_id, note_id, **kwargs)

    def delete_note(self, user_id: str, note_id: str) -> bool:
        return self.note_repo.delete_note(user_id, note_id)

    def list_notes(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.note_repo.list_notes(user_id, limit)

    # ------------------------------------------------------------------
    # LLM expansion
    # ------------------------------------------------------------------
    def expand_note_content(
        self,
        user_input: str,
        existing_note_content: str = "",
    ) -> dict[str, Any]:
        """Expand user input into well-formatted Markdown via the LLM.

        Returns ``{ 'suggestion': str, 'original_input': str }``.
        """
        user_input = (user_input or "").strip()
        if not user_input:
            raise ValueError("Input must not be empty")

        context_snippet = (existing_note_content or "")[-_MAX_NOTE_CONTEXT_CHARS:]
        if context_snippet:
            prompt = (
                f"Existing note content:\n{context_snippet}\n\n"
                f"The user wants to add the following to the note:\n{user_input}"
            )
        else:
            prompt = user_input

        suggestion = self._generate(prompt, NOTE_EXPANSION_SYSTEM_PROMPT)
        return {"suggestion": suggestion.strip(), "original_input": user_input}

    def expand_more(
        self,
        previous_suggestion: str,
        existing_note_content: str = "",
    ) -> dict[str, Any]:
        """Re-prompt the LLM to add more detail to a previous suggestion."""
        context_snippet = (existing_note_content or "")[-_MAX_NOTE_CONTEXT_CHARS:]
        prompt_parts = []
        if context_snippet:
            prompt_parts.append(f"Existing note content:\n{context_snippet}")
        prompt_parts.append(
            f"Previous expansion:\n{previous_suggestion}\n\n"
            "Please expand this further with more detail, additional items, "
            "and richer formatting."
        )
        prompt = "\n\n".join(prompt_parts)

        suggestion = self._generate(prompt, NOTE_EXPANSION_SYSTEM_PROMPT)
        return {"suggestion": suggestion.strip()}

    def accept_suggestion(
        self, user_id: str, note_id: str, suggestion: str
    ) -> dict[str, Any] | None:
        """Append the LLM suggestion to the note."""
        return self.note_repo.append_content(user_id, note_id, suggestion)

    def deny_suggestion(
        self, user_id: str, note_id: str, original_input: str
    ) -> dict[str, Any] | None:
        """Append the user's raw input to the note."""
        return self.note_repo.append_content(user_id, note_id, original_input)
