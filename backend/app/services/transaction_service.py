from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.schemas.transaction import (
    TransactionListResponse,
    TransactionResponse,
    TransactionSummaryResponse,
)
from app.utils.currency import quantize_amount


class TransactionService:
    """Service for querying user-owned transactions and computing Decimal financial summaries."""

    async def list_transactions(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status_filter: str | None = None,
    ) -> TransactionListResponse:
        base_stmt = select(Transaction).where(Transaction.user_id == user_id)
        if status_filter:
            base_stmt = base_stmt.where(Transaction.status == status_filter.upper())

        count_res = await session.execute(
            select(func.count()).select_from(base_stmt.subquery())
        )
        total = int(count_res.scalar_one() or 0)

        stmt = base_stmt.order_by(Transaction.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        rows = list(result.scalars().all())
        return TransactionListResponse(
            total=total,
            transactions=[TransactionResponse.model_validate(row) for row in rows],
        )

    async def get_transaction(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        transaction_id: str,
    ) -> TransactionResponse:
        result = await session.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        tx = result.scalar_one_or_none()
        if tx is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found.",
            )
        if tx.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to view this transaction.",
            )
        return TransactionResponse.model_validate(tx)

    async def get_summary(
        self,
        session: AsyncSession,
        *,
        user_id: str,
    ) -> TransactionSummaryResponse:
        result = await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
        )
        rows = list(result.scalars().all())

        completed_count = 0
        pending_count = 0
        failed_count = 0
        refunded_count = 0
        spent_by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))

        for tx in rows:
            tx_status = tx.status.upper()
            if tx_status == "COMPLETED":
                completed_count += 1
                spent_by_currency[tx.currency] += quantize_amount(tx.amount, tx.currency)
            elif tx_status in {"CREATED", "PENDING_APPROVAL", "APPROVED", "CAPTURE_PENDING"}:
                pending_count += 1
            elif tx_status in {"FAILED", "CANCELLED"}:
                failed_count += 1
            elif tx_status == "REFUNDED":
                refunded_count += 1

        normalized_spent = {
            cur: quantize_amount(total, cur)
            for cur, total in spent_by_currency.items()
        }

        return TransactionSummaryResponse(
            total_count=len(rows),
            completed_count=completed_count,
            pending_count=pending_count,
            failed_count=failed_count,
            refunded_count=refunded_count,
            total_spent_by_currency=normalized_spent,
            recent_transactions=[
                TransactionResponse.model_validate(row) for row in rows[:5]
            ],
        )

