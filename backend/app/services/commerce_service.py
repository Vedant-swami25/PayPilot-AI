from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.orchestrator import CommerceOrchestrator
from app.core.config import Settings, get_settings
from app.models.agent_activity import CommerceWorkflow
from app.models.user import User
from app.schemas.commerce import (
    AgentActivityResponse,
    AgentRunRequest,
    AgentStatusResponse,
    CommerceRequestCreate,
    WorkflowApprovalRequest,
    WorkflowHistoryResponse,
    WorkflowResponse,
)
from app.services.audit_service import AuditService


class CommerceService:
    """Service coordinating AI commerce workflows and activity queries."""

    def __init__(
        self,
        settings: Settings | None = None,
        orchestrator: CommerceOrchestrator | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.orchestrator = orchestrator or CommerceOrchestrator(self.settings)
        self.audit = audit_service or AuditService()

    async def start_commerce_workflow(
        self,
        session: AsyncSession,
        *,
        user: User,
        payload: CommerceRequestCreate | AgentRunRequest,
        ip_address: str | None = None,
    ) -> WorkflowResponse:
        workflow = await self.orchestrator.run_workflow(
            session,
            user=user,
            request_text=payload.request_text,
            budget=payload.budget,
            currency=payload.currency,
            quantity=payload.quantity,
            idempotency_key=payload.idempotency_key,
            ip_address=ip_address,
        )
        return WorkflowResponse.model_validate(workflow)

    async def get_workflow(
        self,
        session: AsyncSession,
        *,
        user: User,
        workflow_id: str,
    ) -> WorkflowResponse:
        workflow = await self.orchestrator._load_workflow(
            session, workflow_id, user.id
        )
        return WorkflowResponse.model_validate(workflow)

    async def get_workflow_status(
        self,
        session: AsyncSession,
        *,
        user: User,
        workflow_id: str,
    ) -> AgentStatusResponse:
        workflow = await self.orchestrator._load_workflow(
            session, workflow_id, user.id
        )
        return AgentStatusResponse(
            workflow_id=workflow.id,
            status=workflow.status,
            current_step=workflow.current_step,
            error_message=workflow.error_message,
            activities=[
                AgentActivityResponse.model_validate(act)
                for act in workflow.activities
            ],
        )

    async def list_workflows(
        self,
        session: AsyncSession,
        *,
        user: User,
        limit: int = 20,
        offset: int = 0,
    ) -> WorkflowHistoryResponse:
        count_res = await session.execute(
            select(func.count(CommerceWorkflow.id)).where(
                CommerceWorkflow.user_id == user.id
            )
        )
        total = int(count_res.scalar_one() or 0)
        result = await session.execute(
            select(CommerceWorkflow)
            .options(selectinload(CommerceWorkflow.activities))
            .where(CommerceWorkflow.user_id == user.id)
            .order_by(CommerceWorkflow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = list(result.scalars().all())
        return WorkflowHistoryResponse(
            total=total,
            workflows=[WorkflowResponse.model_validate(wf) for wf in rows],
        )

    async def list_activities(
        self,
        session: AsyncSession,
        *,
        user: User,
        workflow_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AgentActivityResponse]:
        activities = await self.audit.list_agent_activities(
            session,
            user_id=user.id,
            workflow_id=workflow_id,
            limit=limit,
            offset=offset,
        )
        return [AgentActivityResponse.model_validate(act) for act in activities]

    async def approve_workflow(
        self,
        session: AsyncSession,
        *,
        user: User,
        workflow_id: str,
        payload: WorkflowApprovalRequest,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        result = await self.orchestrator.approve_workflow(
            session,
            user=user,
            workflow_id=workflow_id,
            payload=payload,
            ip_address=ip_address,
        )
        return {
            "workflow": WorkflowResponse.model_validate(result["workflow"]),
            "payment_order": result["payment_order"],
        }

    async def cancel_workflow(
        self,
        session: AsyncSession,
        *,
        user: User,
        workflow_id: str,
        ip_address: str | None = None,
    ) -> WorkflowResponse:
        workflow = await self.orchestrator.cancel_workflow(
            session,
            user=user,
            workflow_id=workflow_id,
            ip_address=ip_address,
        )
        return WorkflowResponse.model_validate(workflow)

