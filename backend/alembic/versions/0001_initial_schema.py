"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-12 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("external_product_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("merchant", sa.String(length=255), nullable=False),
        sa.Column("product_url", sa.String(length=1024), nullable=True),
        sa.Column("availability", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("specifications", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("is_test_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
    )
    op.create_index(op.f("ix_products_category"), "products", ["category"], unique=False)
    op.create_index(
        op.f("ix_products_external_product_id"),
        "products",
        ["external_product_id"],
        unique=True,
    )
    op.create_index(op.f("ix_products_merchant"), "products", ["merchant"], unique=False)
    op.create_index(op.f("ix_products_name"), "products", ["name"], unique=False)

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("paypal_event_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("paypal_order_id", sa.String(length=128), nullable=True),
        sa.Column("paypal_capture_id", sa.String(length=128), nullable=True),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("event_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_events")),
    )
    op.create_index(
        op.f("ix_webhook_events_event_type"),
        "webhook_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_webhook_events_paypal_capture_id"),
        "webhook_events",
        ["paypal_capture_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_webhook_events_paypal_event_id"),
        "webhook_events",
        ["paypal_event_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_webhook_events_paypal_order_id"),
        "webhook_events",
        ["paypal_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_webhook_events_resource_id"),
        "webhook_events",
        ["resource_id"],
        unique=False,
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
    )
    op.create_index(
        op.f("ix_refresh_tokens_family_id"),
        "refresh_tokens",
        ["family_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_refresh_tokens_jti"), "refresh_tokens", ["jti"], unique=True
    )
    op.create_index(
        op.f("ix_refresh_tokens_token_hash"),
        "refresh_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_refresh_tokens_user_id"),
        "refresh_tokens",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "spending_limits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "max_single_transaction", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        sa.Column("daily_limit", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("monthly_limit", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("require_manual_approval", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_spending_limits_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spending_limits")),
    )
    op.create_index(
        op.f("ix_spending_limits_user_id"),
        "spending_limits",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "commerce_workflows",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_step", sa.String(length=64), nullable=False),
        sa.Column("parsed_intent", sa.JSON(), nullable=True),
        sa.Column("discovered_products", sa.JSON(), nullable=True),
        sa.Column("comparison_result", sa.JSON(), nullable=True),
        sa.Column("recommendation", sa.JSON(), nullable=True),
        sa.Column("security_assessment", sa.JSON(), nullable=True),
        sa.Column("approved_product_id", sa.String(length=36), nullable=True),
        sa.Column("approved_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("approved_currency", sa.String(length=3), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("order_id", sa.String(length=36), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_commerce_workflows_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commerce_workflows")),
    )
    op.create_index(
        op.f("ix_commerce_workflows_idempotency_key"),
        "commerce_workflows",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_commerce_workflows_order_id"),
        "commerce_workflows",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commerce_workflows_status"),
        "commerce_workflows",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commerce_workflows_user_id"),
        "commerce_workflows",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("workflow_id", sa.String(length=36), nullable=True),
        sa.Column("paypal_order_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("merchant", sa.String(length=255), nullable=True),
        sa.Column("approval_status", sa.String(length=32), nullable=False),
        sa.Column("approval_url", sa.String(length=1024), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("order_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_orders_product_id_products"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_orders_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
    )
    op.create_index(
        op.f("ix_orders_idempotency_key"), "orders", ["idempotency_key"], unique=True
    )
    op.create_index(
        op.f("ix_orders_paypal_order_id"), "orders", ["paypal_order_id"], unique=True
    )
    op.create_index(op.f("ix_orders_product_id"), "orders", ["product_id"], unique=False)
    op.create_index(op.f("ix_orders_status"), "orders", ["status"], unique=False)
    op.create_index(op.f("ix_orders_user_id"), "orders", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_orders_workflow_id"), "orders", ["workflow_id"], unique=False
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("paypal_capture_id", sa.String(length=128), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payment_method", sa.String(length=64), nullable=False),
        sa.Column("provider_payload", sa.JSON(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_transactions_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_transactions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
    )
    op.create_index(
        op.f("ix_transactions_order_id"), "transactions", ["order_id"], unique=False
    )
    op.create_index(
        op.f("ix_transactions_paypal_capture_id"),
        "transactions",
        ["paypal_capture_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_transactions_status"), "transactions", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_transactions_user_id"), "transactions", ["user_id"], unique=False
    )

    op.create_table(
        "agent_activities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("task", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "execution_time", sa.Numeric(precision=10, scale=4), nullable=False
        ),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_agent_activities_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["commerce_workflows.id"],
            name=op.f("fk_agent_activities_workflow_id_commerce_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_activities")),
    )
    op.create_index(
        op.f("ix_agent_activities_agent_name"),
        "agent_activities",
        ["agent_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_activities_status"),
        "agent_activities",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_activities_user_id"),
        "agent_activities",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_activities_workflow_id"),
        "agent_activities",
        ["workflow_id"],
        unique=False,
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(
        op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False
    )
    op.create_index(
        op.f("ix_audit_logs_resource_id"),
        "audit_logs",
        ["resource_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_logs_resource_type"),
        "audit_logs",
        ["resource_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("agent_activities")
    op.drop_table("transactions")
    op.drop_table("orders")
    op.drop_table("commerce_workflows")
    op.drop_table("spending_limits")
    op.drop_table("refresh_tokens")
    op.drop_table("webhook_events")
    op.drop_table("products")
    op.drop_table("users")

