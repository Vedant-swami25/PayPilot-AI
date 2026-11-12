from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.security import utc_now

if TYPE_CHECKING:
    from app.models.user import User


class CommerceWorkflow(Base):
    """Persisted multi-agent autonomous commerce workflow state."""

    __tablename__ = "commerce_workflows"
    __table_args__ = (
        Index("ix_commerce_workflows_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), index=True, default="PENDING", nullable=False
    )
    current_step: Mapped[str] = mapped_column(
        String(64), default="LEAD_AGENT", nullable=False
    )
    parsed_intent: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    discovered_products: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    comparison_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    recommendation: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    security_assessment: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    approved_product_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    approved_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    order_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="workflows")
    activities: Mapped[list["AgentActivity"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )


class AgentActivity(Base):
    """Per-agent execution telemetry and summary within a commerce workflow."""

    __tablename__ = "agent_activities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("commerce_workflows.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    agent_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    task: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    execution_time: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("0.0000"), nullable=False
    )
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="agent_activities")
    workflow: Mapped["CommerceWorkflow"] = relationship(back_populates="activities")


class AuditLog(Base):
    """Security and financial audit trail."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    user: Mapped["User | None"] = relationship(back_populates="audit_logs")

