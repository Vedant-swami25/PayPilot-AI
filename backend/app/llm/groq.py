from __future__ import annotations

from app.core.config import Settings, get_settings
from app.llm import BaseChatLLMClient


class GroqClient(BaseChatLLMClient):
    """Groq API client for fast inference and lightweight classification tasks."""

    provider_name = "groq"

    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        super().__init__(
            api_key=cfg.groq_api_key.get_secret_value(),
            model=cfg.groq_model,
            base_url=cfg.groq_base_url,
            timeout_seconds=cfg.llm_timeout_seconds,
            max_retries=2,
        )

