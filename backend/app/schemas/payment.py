from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentState(str, Enum):
    CREATED = "CREATED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    CAPTURE_PENDING = "CAPTURE_PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class CreateOrderRequest(BaseModel):
    """Order creation request. Amounts are NEVER trusted from the client; backend computes totals from verified product/workflow data."""

    workflow_id: str | None = Field(
        default=None,
        description="Approved commerce workflow ID.",
    )
    product_id: str | None = Field(
        default=None,
        description="Persisted product ID (required if workflow_id is omitted).",
    )
    quantity: int = Field(default=1, ge=1, le=20)
    expected_amount: Decimal | None = Field(
        default=None,
        gt=0,
        description="Optional client-observed amount for mismatch verification only; backend remains authoritative.",
    )
    expected_currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="Optional client-observed payable currency for safety reconciliation.",
    )
    display_currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="Optional display currency shown to user; PayPal charges the verified payable currency.",
    )
    return_url: str | None = Field(default=None, max_length=1024)
    cancel_url: str | None = Field(default=None, max_length=1024)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("return_url", "cancel_url")
    @classmethod
    def validate_urls(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("Redirect URL must start with http:// or https://")
        return cleaned


class CapturePaymentRequest(BaseModel):
    confirm_capture: bool = Field(
        default=True,
        description="Explicit confirmation to capture an approved PayPal order.",
    )


class CancelPaymentRequest(BaseModel):
    reason: str | None = Field(default="Cancelled by user", max_length=255)


class RefundPaymentRequest(BaseModel):
    reason: str | None = Field(default="Requested by buyer", max_length=255)


class PaymentOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    product_id: str | None = None
    workflow_id: str | None = None
    paypal_order_id: str | None = None
    status: str
    amount: Decimal
    currency: str
    quantity: int
    merchant: str | None = None
    approval_status: str
    approval_url: str | None = None
    approved_at: datetime | None = None
    allowed_actions: list[str] = Field(default_factory=list)
    order_snapshot: dict[str, Any] | None = None
    original_amount: Decimal | None = None
    original_currency: str | None = None
    display_amount: Decimal | None = None
    display_currency: str | None = None
    exchange_rate: Decimal | None = None
    exchange_rate_timestamp: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PaymentQuoteResponse(BaseModel):
    product_id: str
    product_name: str
    merchant: str
    quantity: int
    original_unit_price: Decimal
    original_amount: Decimal
    original_currency: str
    display_amount: Decimal
    display_currency: str
    display_exchange_rate: Decimal
    display_exchange_rate_timestamp: datetime | None = None
    payable_amount: Decimal
    payable_currency: str
    payment_conversion_required: bool = False
    payment_exchange_rate: Decimal = Decimal("1.000000")
    payment_exchange_rate_timestamp: datetime | None = None
    can_checkout: bool = True
    blocking_reason: str | None = None

