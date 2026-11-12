from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)

OutputT = TypeVar("OutputT")


class AgentExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class AgentExecutionError(RuntimeError):
    """Controlled exception raised when an agent fails execution."""

    def __init__(
        self,
        message: str,
        *,
        agent_name: str,
        status: AgentExecutionStatus = AgentExecutionStatus.FAILED,
    ) -> None:
        super().__init__(message)
        self.agent_name = agent_name
        self.status = status


class AgentExecutionResult(BaseModel, Generic[OutputT]):
    agent_name: str
    task: str
    status: AgentExecutionStatus
    execution_time: Decimal = Field(default=Decimal("0.0000"))
    summary: str
    data: OutputT | None = None
    error: str | None = None


class BaseAgent(ABC):
    """Abstract base class for specialized PayPilot AI agents with timeout and telemetry."""

    agent_name: str = "BASE_AGENT"

    def __init__(self, timeout_seconds: float = 45.0) -> None:
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    async def _run(self, *args: Any, **kwargs: Any) -> tuple[str, Any]:
        """Execute agent logic and return (human_summary, structured_output)."""

    async def execute(self, task: str, *args: Any, **kwargs: Any) -> AgentExecutionResult[Any]:
        started = time.perf_counter()
        try:
            summary, data = await asyncio.wait_for(
                self._run(*args, **kwargs),
                timeout=self.timeout_seconds,
            )
            elapsed = Decimal(f"{time.perf_counter() - started:.4f}")
            logger.info(
                "agent_execution_completed",
                agent_name=self.agent_name,
                task=task,
                status=AgentExecutionStatus.SUCCESS.value,
                execution_time=str(elapsed),
            )
            return AgentExecutionResult(
                agent_name=self.agent_name,
                task=task,
                status=AgentExecutionStatus.SUCCESS,
                execution_time=elapsed,
                summary=summary,
                data=data,
            )
        except asyncio.TimeoutError:
            elapsed = Decimal(f"{time.perf_counter() - started:.4f}")
            msg = f"{self.agent_name} timed out after {self.timeout_seconds}s."
            logger.error(
                "agent_execution_timeout",
                agent_name=self.agent_name,
                task=task,
                execution_time=str(elapsed),
            )
            return AgentExecutionResult(
                agent_name=self.agent_name,
                task=task,
                status=AgentExecutionStatus.TIMED_OUT,
                execution_time=elapsed,
                summary=msg,
                error=msg,
            )
        except AgentExecutionError as exc:
            elapsed = Decimal(f"{time.perf_counter() - started:.4f}")
            logger.error(
                "agent_execution_controlled_error",
                agent_name=self.agent_name,
                task=task,
                status=exc.status.value,
                error=str(exc),
            )
            return AgentExecutionResult(
                agent_name=self.agent_name,
                task=task,
                status=exc.status,
                execution_time=elapsed,
                summary=str(exc),
                error=str(exc),
            )
        except Exception as exc:
            elapsed = Decimal(f"{time.perf_counter() - started:.4f}")
            logger.exception(
                "agent_execution_unexpected_error",
                agent_name=self.agent_name,
                task=task,
            )
            return AgentExecutionResult(
                agent_name=self.agent_name,
                task=task,
                status=AgentExecutionStatus.FAILED,
                execution_time=elapsed,
                summary=f"{self.agent_name} failed: {exc}",
                error=str(exc),
            )

