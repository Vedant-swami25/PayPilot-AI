from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.security import utc_now

if TYPE_CHECKING:
    from app.models.transaction import Transaction
    from app.models.user import User


class Order(Base):
    """Backend-controlled purchase order linked to a PayPal Orders API v2 order."""

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("quantity >= 1 AND quantity <= 100", name="quantity_range"),
        Index("ix_orders_user_created", "user_id", "created_at"),
        Index(
            "ix_orders_user_status_currency_created",
            "user_id",
            "status",
            "currency",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="SET NULL"), index=True, nullable=True
    )
    workflow_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    paypal_order_id: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), index=True, default="CREATED", nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approval_status: Mapped[str] = mapped_column(
        String(32), default="PENDING", nullable=False
    )
    approval_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    order_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="orders")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

