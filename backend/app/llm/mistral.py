from __future__ import annotations

from app.core.config import Settings, get_settings
from app.llm import BaseChatLLMClient


class MistralClient(BaseChatLLMClient):
    """Mistral API client for structured analysis and contextual processing."""

    provider_name = "mistral"

    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        super().__init__(
            api_key=cfg.mistral_api_key.get_secret_value(),
            model=cfg.mistral_model,
            base_url=cfg.mistral_base_url,
            timeout_seconds=cfg.llm_timeout_seconds,
            max_retries=2,
        )

