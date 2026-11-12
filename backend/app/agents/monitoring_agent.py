from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AgentExecutionResult, BaseAgent
from app.core.config import Settings, get_settings
from app.models.agent_activity import AgentActivity
from app.services.audit_service import AuditService
from app.services.transaction_service import TransactionService


class MonitoringSummary(BaseModel):
    workflow_id: str
    workflow_status: str
    failed_steps: list[str] = Field(default_factory=list)
    total_execution_time: Decimal = Decimal("0.0000")
    activities_recorded: int = 0
    transaction_summary: dict[str, Any] = Field(default_factory=dict)


class MonitoringAgent(BaseAgent):
    """Agent responsible for tracking execution telemetry, failures, and transaction audit history."""

    agent_name = "MONITORING_AGENT"

    def __init__(
        self,
        audit_service: AuditService | None = None,
        transaction_service: TransactionService | None = None,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        super().__init__(timeout_seconds=cfg.agent_timeout_seconds)
        self.audit = audit_service or AuditService()
        self.transactions = transaction_service or TransactionService()

    async def record_step(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        workflow_id: str,
        result: AgentExecutionResult[Any],
        details: dict[str, Any] | None = None,
    ) -> AgentActivity:
        return await self.audit.record_agent_activity(
            session,
            user_id=user_id,
            workflow_id=workflow_id,
            agent_name=result.agent_name,
            task=result.task,
            status=result.status.value,
            execution_time=result.execution_time,
            result_summary=result.summary,
            details=details,
        )

    async def _run(self, *args: Any, **kwargs: Any) -> tuple[str, MonitoringSummary]:
        session: AsyncSession = kwargs["session"]
        user_id: str = kwargs["user_id"]
        workflow_id: str = kwargs["workflow_id"]
        workflow_status: str = kwargs["workflow_status"]
        ip_address: str | None = kwargs.get("ip_address")

        res = await session.execute(
            select(AgentActivity)
            .where(
                AgentActivity.user_id == user_id,
                AgentActivity.workflow_id == workflow_id,
            )
            .order_by(AgentActivity.created_at.asc())
        )
        activities = list(res.scalars().all())
        failed_steps = [
            act.agent_name
            for act in activities
            if act.status in {"FAILED", "TIMED_OUT", "BLOCKED", "NOT_CONFIGURED"}
        ]
        total_time = sum(
            (act.execution_time for act in activities), Decimal("0.0000")
        )
        tx_summary = await self.transactions.get_summary(session, user_id=user_id)

        await self.audit.record_audit_log(
            session,
            user_id=user_id,
            action="WORKFLOW_MONITORING_SNAPSHOT",
            resource_type="commerce_workflow",
            resource_id=workflow_id,
            status=workflow_status,
            ip_address=ip_address,
            details={
                "failed_steps": failed_steps,
                "activities_recorded": len(activities),
                "total_execution_time": str(total_time),
            },
        )

        summary_obj = MonitoringSummary(
            workflow_id=workflow_id,
            workflow_status=workflow_status,
            failed_steps=failed_steps,
            total_execution_time=total_time,
            activities_recorded=len(activities),
            transaction_summary=tx_summary.model_dump(mode="json"),
        )
        summary_text = (
            f"Recorded {len(activities)} agent steps in {total_time}s; "
            f"workflow status={workflow_status}, failed_steps={len(failed_steps)}."
        )
        return summary_text, summary_obj

