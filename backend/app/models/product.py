from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.security import utc_now


class Product(Base):
    """Discovered commerce product persisted from verified product providers."""

    __tablename__ = "products"
    __table_args__ = (CheckConstraint("price > 0", name="price_positive"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    external_product_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    merchant: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    product_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    availability: Mapped[str] = mapped_column(String(64), default="IN_STOCK", nullable=False)
    category: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    specifications: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    provider: Mapped[str] = mapped_column(String(64), default="channel3", nullable=False)
    is_test_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

