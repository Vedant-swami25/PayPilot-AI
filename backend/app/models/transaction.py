from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.security import utc_now

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.user import User


class Transaction(Base):
    """Payment transaction record reflecting verified PayPal order/capture state."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_transactions_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    paypal_capture_id: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    payment_method: Mapped[str] = mapped_column(
        String(64), default="paypal", nullable=False
    )
    provider_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="transactions")
    order: Mapped["Order"] = relationship(back_populates="transactions")


class WebhookEvent(Base):
    """Idempotent log of verified PayPal webhook events."""

    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    paypal_event_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    paypal_order_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    paypal_capture_id: Mapped[str | None] = mapped_column(
        String(128), index=True, nullable=True
    )
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(32), default="RECEIVED", nullable=False
    )
    event_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

