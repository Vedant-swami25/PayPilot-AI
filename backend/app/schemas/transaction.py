from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    order_id: str
    paypal_capture_id: str | None = None
    amount: Decimal
    currency: str
    status: str
    payment_method: str
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class TransactionListResponse(BaseModel):
    total: int
    transactions: list[TransactionResponse]


class TransactionSummaryResponse(BaseModel):
    total_count: int
    completed_count: int
    pending_count: int
    failed_count: int
    refunded_count: int
    total_spent_by_currency: dict[str, Decimal] = Field(default_factory=dict)
    recent_transactions: list[TransactionResponse] = Field(default_factory=list)


class WebhookResponse(BaseModel):
    received: bool
    event_id: str
    event_type: str
    status: str
    duplicate: bool = False
    details: dict[str, Any] | None = None

