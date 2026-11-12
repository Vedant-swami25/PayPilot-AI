from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_commerce_service, get_current_user
from app.core.database import get_db
from app.core.security import get_client_ip
from app.models.user import User
from app.schemas.commerce import (
    AgentActivityResponse,
    AgentRunRequest,
    AgentStatusResponse,
    WorkflowResponse,
)
from app.services.commerce_service import CommerceService

router = APIRouter(prefix="/agents", tags=["AI Agents"])


@router.post(
    "/run",
    response_model=WorkflowResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute the multi-agent AI pipeline for a shopping request",
)
async def run_agents(
    request: Request,
    payload: AgentRunRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    commerce_service: CommerceService = Depends(get_commerce_service),
) -> WorkflowResponse:
    return await commerce_service.start_commerce_workflow(
        session,
        user=current_user,
        payload=payload,
        ip_address=get_client_ip(request),
    )


@router.get(
    "/status/{workflow_id}",
    response_model=AgentStatusResponse,
    summary="Retrieve step-by-step agent execution status for a workflow",
)
async def get_agent_status(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    commerce_service: CommerceService = Depends(get_commerce_service),
) -> AgentStatusResponse:
    return await commerce_service.get_workflow_status(
        session, user=current_user, workflow_id=workflow_id
    )


@router.get(
    "/activity",
    response_model=list[AgentActivityResponse],
    summary="List recent AI agent execution activity logs for the current user",
)
async def get_agent_activity(
    workflow_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    commerce_service: CommerceService = Depends(get_commerce_service),
) -> list[AgentActivityResponse]:
    return await commerce_service.list_activities(
        session,
        user=current_user,
        workflow_id=workflow_id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/cancel/{workflow_id}",
    response_model=WorkflowResponse,
    summary="Cancel an active or awaiting-approval agent workflow",
)
async def cancel_agent_workflow(
    request: Request,
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    commerce_service: CommerceService = Depends(get_commerce_service),
) -> WorkflowResponse:
    return await commerce_service.cancel_workflow(
        session,
        user=current_user,
        workflow_id=workflow_id,
        ip_address=get_client_ip(request),
    )

