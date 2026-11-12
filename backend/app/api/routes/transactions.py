from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_transaction_service
from app.core.database import get_db
from app.models.user import User
from app.schemas.transaction import (
    TransactionListResponse,
    TransactionResponse,
    TransactionSummaryResponse,
)
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get(
    "",
    response_model=TransactionListResponse,
    summary="List payment transactions belonging to the authenticated user",
)
async def list_transactions(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    transaction_service: TransactionService = Depends(get_transaction_service),
) -> TransactionListResponse:
    return await transaction_service.list_transactions(
        session,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        status_filter=status,
    )


@router.get(
    "/summary",
    response_model=TransactionSummaryResponse,
    summary="Retrieve transaction counts and exact Decimal spend totals by currency",
)
async def get_transaction_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    transaction_service: TransactionService = Depends(get_transaction_service),
) -> TransactionSummaryResponse:
    return await transaction_service.get_summary(session, user_id=current_user.id)


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Retrieve details of a specific user-owned transaction",
)
async def get_transaction(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    transaction_service: TransactionService = Depends(get_transaction_service),
) -> TransactionResponse:
    return await transaction_service.get_transaction(
        session,
        user_id=current_user.id,
        transaction_id=transaction_id,
    )

