from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.agent_activity import AgentActivity, AuditLog
from app.utils.helpers import truncate_text

logger = get_logger(__name__)


class AuditService:
    """Service responsible for persisting immutable security and agent activity records."""

    async def record_audit_log(
        self,
        session: AsyncSession,
        *,
        user_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        status: str = "SUCCESS",
        ip_address: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            ip_address=ip_address,
            details=details,
        )
        session.add(entry)
        await session.flush()
        logger.info(
            "audit_log_recorded",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            user_id=user_id,
        )
        return entry

    async def record_agent_activity(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        workflow_id: str,
        agent_name: str,
        task: str,
        status: str,
        execution_time: Decimal,
        result_summary: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AgentActivity:
        activity = AgentActivity(
            user_id=user_id,
            workflow_id=workflow_id,
            agent_name=agent_name,
            task=truncate_text(task, 255) or task,
            status=status,
            execution_time=execution_time,
            result_summary=truncate_text(result_summary, 2000),
            details=details,
        )
        session.add(activity)
        await session.flush()
        return activity

    async def list_agent_activities(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        workflow_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AgentActivity]:
        stmt = select(AgentActivity).where(AgentActivity.user_id == user_id)
        if workflow_id:
            stmt = stmt.where(AgentActivity.workflow_id == workflow_id)
        stmt = stmt.order_by(AgentActivity.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

