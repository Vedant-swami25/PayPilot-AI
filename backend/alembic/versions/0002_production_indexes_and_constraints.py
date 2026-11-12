"""production indexes and constraints

Revision ID: 0002_production_indexes
Revises: 0001_initial_schema
Create Date: 2026-11-12 15:50:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_production_indexes"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_orders_user_created", "orders", ["user_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_orders_user_status_currency_created",
        "orders",
        ["user_id", "status", "currency", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_transactions_user_created",
        "transactions",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_commerce_workflows_user_created",
        "commerce_workflows",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_user_created",
        "audit_logs",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_check_constraint(
        "amount_positive", "orders", "amount > 0"
    )
    op.create_check_constraint(
        "quantity_range", "orders", "quantity >= 1 AND quantity <= 100"
    )
    op.create_check_constraint(
        "amount_positive", "transactions", "amount > 0"
    )
    op.create_check_constraint(
        "price_positive", "products", "price > 0"
    )
    op.create_check_constraint(
        "limits_positive",
        "spending_limits",
        "max_single_transaction > 0 AND daily_limit > 0 AND monthly_limit > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_spending_limits_limits_positive"),
        "spending_limits",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_products_price_positive"), "products", type_="check"
    )
    op.drop_constraint(
        op.f("ck_transactions_amount_positive"), "transactions", type_="check"
    )
    op.drop_constraint(
        op.f("ck_orders_quantity_range"), "orders", type_="check"
    )
    op.drop_constraint(
        op.f("ck_orders_amount_positive"), "orders", type_="check"
    )

    op.drop_index("ix_audit_logs_user_created", table_name="audit_logs")
    op.drop_index(
        "ix_commerce_workflows_user_created", table_name="commerce_workflows"
    )
    op.drop_index("ix_transactions_user_created", table_name="transactions")
    op.drop_index("ix_orders_user_status_currency_created", table_name="orders")
    op.drop_index("ix_orders_user_created", table_name="orders")

