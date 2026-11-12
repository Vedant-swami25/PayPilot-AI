from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.currency import validate_currency_code


class CommerceRequestCreate(BaseModel):
    request_text: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        examples=["Find me noise cancelling wireless headphones under $300 USD"],
    )
    budget: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    quantity: int = Field(default=1, ge=1, le=20)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)
    auto_create_order: bool = Field(
        default=False,
        description="Only valid after explicit approval via /approve; ignored during initial discovery.",
    )

    @field_validator("currency")
    @classmethod
    def check_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_currency_code(value)


class AgentRunRequest(BaseModel):
    request_text: str = Field(..., min_length=3, max_length=2000)
    budget: Decimal | None = Field(default=None, gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    quantity: int = Field(default=1, ge=1, le=20)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("currency")
    @classmethod
    def check_currency(cls, value: str) -> str:
        return validate_currency_code(value)


class WorkflowApprovalRequest(BaseModel):
    product_id: str | None = Field(
        default=None,
        description="Optional product ID override from the workflow's discovered products. Defaults to recommended product.",
    )
    quantity: int = Field(default=1, ge=1, le=20)
    confirm_purchase: bool = Field(
        ...,
        description="Explicit user confirmation authorizing order preparation for checkout.",
    )
    create_paypal_order: bool = Field(
        default=True,
        description="Whether to immediately create a PayPal order after user approval.",
    )
    return_url: str | None = Field(default=None, max_length=1024)
    cancel_url: str | None = Field(default=None, max_length=1024)


class AgentActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    workflow_id: str
    agent_name: str
    task: str
    status: str
    execution_time: Decimal
    result_summary: str | None = None
    details: dict[str, Any] | None = None
    created_at: datetime


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    request_text: str
    status: str
    current_step: str
    parsed_intent: dict[str, Any] | None = None
    discovered_products: list[dict[str, Any]] | None = None
    comparison_result: dict[str, Any] | None = None
    recommendation: dict[str, Any] | None = None
    security_assessment: dict[str, Any] | None = None
    approved_product_id: str | None = None
    approved_amount: Decimal | None = None
    approved_currency: str | None = None
    approved_at: datetime | None = None
    order_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    activities: list[AgentActivityResponse] = Field(default_factory=list)


class WorkflowHistoryResponse(BaseModel):
    total: int
    workflows: list[WorkflowResponse]


class AgentStatusResponse(BaseModel):
    workflow_id: str
    status: str
    current_step: str
    error_message: str | None = None
    activities: list[AgentActivityResponse]

