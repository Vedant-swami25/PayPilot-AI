from __future__ import annotations

import asyncio
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.logging import get_logger
from app.core.observability import observability
from app.utils.helpers import extract_json_object

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class CircuitBreaker:
    """Thread-safe provider circuit breaker preventing cascading upstream stalls."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> str:
        with self._lock:
            if self._opened_at is None:
                return "CLOSED"
            if (time.monotonic() - self._opened_at) >= self.recovery_timeout:
                return "HALF_OPEN"
            return "OPEN"

    def allow_request(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return True
            if (time.monotonic() - self._opened_at) >= self.recovery_timeout:
                return True
            return False

    def record_success(self) -> str:
        with self._lock:
            self._failures = 0
            self._opened_at = None
            return "CLOSED"

    def record_failure(self) -> str:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()
                return "OPEN"
            return "CLOSED"

    def reset(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None


_CIRCUIT_BREAKERS: dict[str, CircuitBreaker] = {}
_BREAKER_REGISTRY_LOCK = threading.Lock()


def get_provider_circuit_breaker(provider_name: str) -> CircuitBreaker:
    with _BREAKER_REGISTRY_LOCK:
        breaker = _CIRCUIT_BREAKERS.get(provider_name)
        if breaker is None:
            breaker = CircuitBreaker()
            _CIRCUIT_BREAKERS[provider_name] = breaker
        return breaker


def reset_circuit_breakers() -> None:
    """Reset all provider circuit breakers (used in tests and graceful resets)."""
    with _BREAKER_REGISTRY_LOCK:
        for breaker in _CIRCUIT_BREAKERS.values():
            breaker.reset()


class LLMError(RuntimeError):
    """Base error for LLM provider failures."""

    def __init__(self, message: str, provider: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class LLMNotConfiguredError(LLMError):
    """Raised when a required LLM provider API key or model identifier is missing."""


class LLMTimeoutError(LLMError):
    """Raised when an LLM API call exceeds the configured timeout."""


class LLMProviderError(LLMError):
    """Raised when an upstream LLM provider returns an HTTP or network error."""


class LLMResponseParseError(LLMError):
    """Raised when an LLM output cannot be parsed into the expected structured schema."""


@dataclass(slots=True)
class LLMResponse:
    provider: str
    model: str
    content: str
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw_usage: dict[str, Any] = field(default_factory=dict)


class BaseChatLLMClient:
    """Shared async HTTP chat completion client with retries, timeouts, and telemetry."""

    provider_name: str = "base"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self._api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def is_configured(self) -> bool:
        """Return True only when both API key and model identifier are present."""
        return bool(self._api_key and self.model)

    def health_status(self) -> dict[str, Any]:
        """Return safe configuration status without exposing credentials."""
        if not self._api_key and not self.model:
            return {
                "provider": self.provider_name,
                "status": "NOT_CONFIGURED",
                "model": None,
                "detail": "API key and model identifier are not configured.",
            }
        if not self._api_key:
            return {
                "provider": self.provider_name,
                "status": "NOT_CONFIGURED",
                "model": self.model or None,
                "detail": "API key is not configured.",
            }
        if not self.model:
            return {
                "provider": self.provider_name,
                "status": "NOT_CONFIGURED",
                "model": None,
                "detail": "Model identifier is not configured.",
            }
        return {
            "provider": self.provider_name,
            "status": "CONFIGURED",
            "model": self.model,
            "circuit_state": get_provider_circuit_breaker(self.provider_name).state,
            "detail": "Credentials and model configured.",
        }

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _build_payload(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    @staticmethod
    def _compute_backoff(attempt: int, retry_after_header: str | None = None) -> float:
        if retry_after_header:
            try:
                parsed = float(retry_after_header.strip())
                if 0 < parsed <= 5.0:
                    return parsed
                if parsed > 5.0:
                    return 5.0
            except ValueError:
                pass
        base = 0.5 * (2**attempt)
        return round(base * random.uniform(0.5, 1.5), 3)

    async def chat_completion(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        json_mode: bool = True,
    ) -> LLMResponse:
        """Execute chat completion with circuit breaker and jittered retry policy."""
        if not self.is_configured():
            raise LLMNotConfiguredError(
                f"{self.provider_name} is not configured (missing API key or model).",
                provider=self.provider_name,
            )

        breaker = get_provider_circuit_breaker(self.provider_name)
        if not breaker.allow_request():
            observability.record_llm_call(
                self.provider_name,
                success=False,
                circuit_rejected=True,
                circuit_state="OPEN",
            )
            raise LLMProviderError(
                f"{self.provider_name} circuit breaker is OPEN due to repeated upstream failures.",
                provider=self.provider_name,
                status_code=503,
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        url = f"{self.base_url}/chat/completions"
        use_json_mode = json_mode

        last_error: LLMError | None = None

        for attempt in range(self.max_retries + 1):
            payload = self._build_payload(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=use_json_mode,
            )
            started = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        url,
                        headers=self._build_headers(),
                        json=payload,
                    )
                latency_ms = round((time.perf_counter() - started) * 1000.0, 2)

                if response.status_code == 400 and use_json_mode and "response_format" in response.text:
                    # Some model deployments reject response_format; retry once without it.
                    use_json_mode = False
                    continue

                if response.status_code in {429, 500, 502, 503, 504}:
                    last_error = LLMProviderError(
                        f"{self.provider_name} returned transient status {response.status_code}.",
                        provider=self.provider_name,
                        status_code=response.status_code,
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(
                            self._compute_backoff(attempt, response.headers.get("retry-after"))
                        )
                        continue
                    c_state = breaker.record_failure()
                    observability.record_llm_call(
                        self.provider_name,
                        success=False,
                        latency_ms=latency_ms,
                        circuit_state=c_state,
                    )
                    raise last_error

                if response.status_code >= 400:
                    observability.record_llm_call(
                        self.provider_name,
                        success=False,
                        latency_ms=latency_ms,
                        circuit_state=breaker.state,
                    )
                    raise LLMProviderError(
                        f"{self.provider_name} request failed with HTTP {response.status_code}.",
                        provider=self.provider_name,
                        status_code=response.status_code,
                    )

                data = response.json()
                choices = data.get("choices") or []
                if not choices:
                    raise LLMResponseParseError(
                        f"{self.provider_name} returned empty choices.",
                        provider=self.provider_name,
                    )

                message = choices[0].get("message") or {}
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise LLMResponseParseError(
                        f"{self.provider_name} returned empty message content.",
                        provider=self.provider_name,
                    )

                usage = data.get("usage") or {}
                result = LLMResponse(
                    provider=self.provider_name,
                    model=data.get("model") or self.model,
                    content=content,
                    latency_ms=latency_ms,
                    prompt_tokens=int(usage.get("prompt_tokens") or 0),
                    completion_tokens=int(usage.get("completion_tokens") or 0),
                    total_tokens=int(usage.get("total_tokens") or 0),
                    raw_usage=usage if isinstance(usage, dict) else {},
                )
                c_state = breaker.record_success()
                observability.record_llm_call(
                    self.provider_name,
                    success=True,
                    latency_ms=result.latency_ms,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    total_tokens=result.total_tokens,
                    circuit_state=c_state,
                )

                logger.info(
                    "llm_completion_success",
                    provider=self.provider_name,
                    model=result.model,
                    latency_ms=result.latency_ms,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    total_tokens=result.total_tokens,
                )
                return result

            except httpx.TimeoutException as exc:
                latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
                last_error = LLMTimeoutError(
                    f"{self.provider_name} request timed out after {self.timeout_seconds}s.",
                    provider=self.provider_name,
                )
                logger.warning(
                    "llm_completion_timeout",
                    provider=self.provider_name,
                    attempt=attempt + 1,
                    timeout_seconds=self.timeout_seconds,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self._compute_backoff(attempt))
                    continue
                c_state = breaker.record_failure()
                observability.record_llm_call(
                    self.provider_name,
                    success=False,
                    latency_ms=latency_ms,
                    timed_out=True,
                    circuit_state=c_state,
                )
                raise last_error from exc
            except httpx.RequestError as exc:
                latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
                last_error = LLMProviderError(
                    f"{self.provider_name} network error: {exc.__class__.__name__}",
                    provider=self.provider_name,
                )
                logger.warning(
                    "llm_completion_network_error",
                    provider=self.provider_name,
                    attempt=attempt + 1,
                    error_type=exc.__class__.__name__,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self._compute_backoff(attempt))
                    continue
                c_state = breaker.record_failure()
                observability.record_llm_call(
                    self.provider_name,
                    success=False,
                    latency_ms=latency_ms,
                    circuit_state=c_state,
                )
                raise last_error from exc

        raise last_error or LLMProviderError(
            f"{self.provider_name} failed after retries.",
            provider=self.provider_name,
        )

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        temperature: float = 0.1,
        max_tokens: int = 1200,
    ) -> tuple[T, LLMResponse]:
        """Call chat_completion and parse/validate output into a Pydantic model with 1 JSON repair attempt."""
        last_exc: Exception | None = None
        last_model = self.model

        for parse_attempt in range(2):
            effective_system = system_prompt
            effective_temp = temperature
            if parse_attempt == 1:
                effective_system = (
                    f"{system_prompt}\n\n"
                    "CRITICAL FORMAT CORRECTION: Your previous output was not valid JSON matching the schema. "
                    "Respond ONLY with a single raw JSON object with no markdown fences or extra text."
                )
                effective_temp = 0.0

            response = await self.chat_completion(
                system_prompt=effective_system,
                user_prompt=user_prompt,
                temperature=effective_temp,
                max_tokens=max_tokens,
                json_mode=True,
            )
            last_model = response.model
            try:
                raw_obj = extract_json_object(response.content)
                parsed = schema.model_validate(raw_obj)
                return parsed, response
            except (ValueError, ValidationError) as exc:
                last_exc = exc
                logger.warning(
                    "llm_structured_parse_retry" if parse_attempt == 0 else "llm_structured_parse_failed",
                    provider=self.provider_name,
                    model=last_model,
                    attempt=parse_attempt + 1,
                    error=str(exc),
                )

        raise LLMResponseParseError(
            f"{self.provider_name} returned invalid structured JSON: {last_exc}",
            provider=self.provider_name,
        ) from last_exc

    async def verify_connectivity(self) -> dict[str, Any]:
        """Check whether provider API endpoint is reachable with configured credentials."""
        status_info = self.health_status()
        if status_info["status"] != "CONFIGURED":
            return status_info

        try:
            async with httpx.AsyncClient(timeout=min(self.timeout_seconds, 8.0)) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
            if resp.status_code < 400:
                status_info["status"] = "HEALTHY"
                status_info["detail"] = "Provider reachable and authenticated."
            else:
                status_info["status"] = "UNHEALTHY"
                status_info["detail"] = f"Provider check returned HTTP {resp.status_code}."
        except httpx.TimeoutException:
            status_info["status"] = "UNHEALTHY"
            status_info["detail"] = "Provider health check timed out."
        except httpx.RequestError as exc:
            status_info["status"] = "UNHEALTHY"
            status_info["detail"] = f"Provider network error: {exc.__class__.__name__}."
        return status_info

