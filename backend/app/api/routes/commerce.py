from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_commerce_service, get_current_user
from app.core.database import get_db
from app.core.security import get_client_ip
from app.models.user import User
from app.schemas.commerce import (
    CommerceRequestCreate,
    WorkflowApprovalRequest,
    WorkflowHistoryResponse,
    WorkflowResponse,
)
from app.schemas.payment import PaymentOrderResponse
from app.services.commerce_service import CommerceService

router = APIRouter(prefix="/commerce", tags=["Autonomous Commerce"])


class WorkflowApprovalResponse(BaseModel):
    workflow: WorkflowResponse
    payment_order: PaymentOrderResponse | None = None


@router.post(
    "/request",
    response_model=WorkflowResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit an autonomous shopping request to the PayPilot AI orchestration engine",
)
async def submit_commerce_request(
    request: Request,
    payload: CommerceRequestCreate,
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
    "/workflows/{workflow_id}",
    response_model=WorkflowResponse,
    summary="Retrieve full state and agent outputs for a commerce workflow",
)
async def get_commerce_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    commerce_service: CommerceService = Depends(get_commerce_service),
) -> WorkflowResponse:
    return await commerce_service.get_workflow(
        session, user=current_user, workflow_id=workflow_id
    )


@router.get(
    "/history",
    response_model=WorkflowHistoryResponse,
    summary="List historical commerce workflows for the authenticated user",
)
async def get_commerce_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    commerce_service: CommerceService = Depends(get_commerce_service),
) -> WorkflowHistoryResponse:
    return await commerce_service.list_workflows(
        session, user=current_user, limit=limit, offset=offset
    )


@router.post(
    "/workflows/{workflow_id}/approve",
    response_model=WorkflowApprovalResponse,
    summary="Explicitly approve a recommended purchase and optionally prepare PayPal checkout",
)
async def approve_commerce_workflow(
    request: Request,
    workflow_id: str,
    payload: WorkflowApprovalRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    commerce_service: CommerceService = Depends(get_commerce_service),
) -> dict[str, Any]:
    return await commerce_service.approve_workflow(
        session,
        user=current_user,
        workflow_id=workflow_id,
        payload=payload,
        ip_address=get_client_ip(request),
    )

