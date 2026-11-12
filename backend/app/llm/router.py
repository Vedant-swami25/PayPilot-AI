from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.llm import (
    BaseChatLLMClient,
    LLMNotConfiguredError,
    LLMResponse,
)
from app.llm.groq import GroqClient
from app.llm.mistral import MistralClient
from app.llm.nemotron import NemotronClient

T = TypeVar("T", bound=BaseModel)


class LLMTaskRole(str, Enum):
    """Logical task roles routed explicitly without silent primary substitution."""

    PRIMARY_ORCHESTRATION = "primary_orchestration"
    STRUCTURED_ANALYSIS = "structured_analysis"
    FAST_CLASSIFICATION = "fast_classification"


class LLMRouter:
    """Explicit router across NVIDIA Nemotron (primary), Mistral, and Groq."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.nemotron = NemotronClient(self.settings)
        self.mistral = MistralClient(self.settings)
        self.groq = GroqClient(self.settings)

    def get_client(self, role: LLMTaskRole) -> BaseChatLLMClient:
        """Return the designated provider client for the given role."""
        if role == LLMTaskRole.PRIMARY_ORCHESTRATION:
            return self.nemotron
        if role == LLMTaskRole.STRUCTURED_ANALYSIS:
            return self.mistral
        if role == LLMTaskRole.FAST_CLASSIFICATION:
            return self.groq
        raise ValueError(f"Unsupported LLMTaskRole: {role}")

    async def generate_primary_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        temperature: float = 0.1,
        max_tokens: int = 1200,
    ) -> tuple[T, LLMResponse]:
        """Execute primary reasoning strictly on NVIDIA Nemotron without silent fallback."""
        if not self.nemotron.is_configured():
            raise LLMNotConfiguredError(
                "NVIDIA Nemotron is not configured. Set NVIDIA_API_KEY and NVIDIA_MODEL.",
                provider=self.nemotron.provider_name,
            )
        return await self.nemotron.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def generate_supporting_structured(
        self,
        *,
        role: LLMTaskRole,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> tuple[T, LLMResponse]:
        """Execute supporting specialist reasoning on its designated provider."""
        if role == LLMTaskRole.PRIMARY_ORCHESTRATION:
            return await self.generate_primary_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        client = self.get_client(role)
        if not client.is_configured():
            raise LLMNotConfiguredError(
                f"{client.provider_name} is not configured for role '{role.value}'.",
                provider=client.provider_name,
            )
        return await client.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def check_all_providers(self, verify_remote: bool = False) -> dict[str, Any]:
        """Inspect status of all LLM providers without leaking credentials."""
        clients = [self.nemotron, self.mistral, self.groq]
        if not verify_remote:
            results = {c.provider_name: c.health_status() for c in clients}
        else:
            checks = await asyncio.gather(*(c.verify_connectivity() for c in clients))
            results = {item["provider"]: item for item in checks}

        nemotron_status = results[self.nemotron.provider_name]["status"]
        overall = "HEALTHY" if nemotron_status in {"CONFIGURED", "HEALTHY"} else nemotron_status
        return {
            "status": overall,
            "primary_provider": self.nemotron.provider_name,
            "providers": results,
        }

