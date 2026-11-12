from __future__ import annotations

from app.core.config import Settings, get_settings
from app.llm import BaseChatLLMClient


class NemotronClient(BaseChatLLMClient):
    """NVIDIA Nemotron client serving as primary orchestration and reasoning model."""

    provider_name = "nvidia_nemotron"

    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        super().__init__(
            api_key=cfg.nvidia_api_key.get_secret_value(),
            model=cfg.nvidia_model,
            base_url=cfg.nvidia_base_url,
            timeout_seconds=cfg.llm_timeout_seconds,
            max_retries=2,
        )

