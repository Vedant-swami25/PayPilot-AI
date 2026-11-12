from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _ProviderTelemetry:
    calls: int = 0
    errors: int = 0
    timeouts: int = 0
    circuit_rejects: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    circuit_state: str = "CLOSED"


class ObservabilityRegistry:
    """Thread-safe in-memory runtime telemetry for API, AI, payments, and product search."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._http_total = 0
        self._http_2xx_3xx = 0
        self._http_4xx = 0
        self._http_5xx = 0
        self._http_latency_ms_total = 0.0
        self._providers: dict[str, _ProviderTelemetry] = {}
        self._counters: dict[str, int] = field(default_factory=dict) if False else {}

    def record_http_request(self, status_code: int, latency_ms: float) -> None:
        with self._lock:
            self._http_total += 1
            self._http_latency_ms_total += max(0.0, latency_ms)
            if status_code >= 500:
                self._http_5xx += 1
            elif status_code >= 400:
                self._http_4xx += 1
            else:
                self._http_2xx_3xx += 1

    def record_llm_call(
        self,
        provider: str,
        *,
        success: bool,
        latency_ms: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        timed_out: bool = False,
        circuit_rejected: bool = False,
        circuit_state: str = "CLOSED",
    ) -> None:
        with self._lock:
            stat = self._providers.setdefault(provider, _ProviderTelemetry())
            stat.calls += 1
            stat.circuit_state = circuit_state
            stat.total_latency_ms += max(0.0, latency_ms)
            if success:
                stat.prompt_tokens += max(0, prompt_tokens)
                stat.completion_tokens += max(0, completion_tokens)
                stat.total_tokens += max(0, total_tokens)
            else:
                stat.errors += 1
                if timed_out:
                    stat.timeouts += 1
                if circuit_rejected:
                    stat.circuit_rejects += 1

    def set_circuit_state(self, provider: str, state: str) -> None:
        with self._lock:
            stat = self._providers.setdefault(provider, _ProviderTelemetry())
            stat.circuit_state = state

    def increment(self, metric_name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[metric_name] = self._counters.get(metric_name, 0) + amount

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            avg_http = (
                round(self._http_latency_ms_total / self._http_total, 2)
                if self._http_total
                else 0.0
            )
            providers_out: dict[str, Any] = {}
            for name, stat in self._providers.items():
                providers_out[name] = {
                    "calls": stat.calls,
                    "errors": stat.errors,
                    "timeouts": stat.timeouts,
                    "circuit_rejects": stat.circuit_rejects,
                    "circuit_state": stat.circuit_state,
                    "prompt_tokens": stat.prompt_tokens,
                    "completion_tokens": stat.completion_tokens,
                    "total_tokens": stat.total_tokens,
                    "avg_latency_ms": (
                        round(stat.total_latency_ms / stat.calls, 2) if stat.calls else 0.0
                    ),
                }
            return {
                "http": {
                    "total_requests": self._http_total,
                    "success_responses": self._http_2xx_3xx,
                    "client_errors": self._http_4xx,
                    "server_errors": self._http_5xx,
                    "avg_latency_ms": avg_http,
                },
                "ai_providers": providers_out,
                "counters": dict(self._counters),
            }

    def reset(self) -> None:
        with self._lock:
            self._http_total = 0
            self._http_2xx_3xx = 0
            self._http_4xx = 0
            self._http_5xx = 0
            self._http_latency_ms_total = 0.0
            self._providers.clear()
            self._counters.clear()


observability = ObservabilityRegistry()

