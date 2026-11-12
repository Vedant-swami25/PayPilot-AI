from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class PayPalLink(BaseModel):
    href: str
    rel: str
    method: str | None = None


class PayPalAmount(BaseModel):
    currency_code: str
    value: str


class PayPalOrderCreateResult(BaseModel):
    paypal_order_id: str
    status: str
    approval_url: str | None = None
    links: list[PayPalLink] = Field(default_factory=list)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class PayPalOrderDetails(BaseModel):
    paypal_order_id: str
    status: str
    intent: str | None = None
    amount_value: Decimal | None = None
    currency_code: str | None = None
    payee_merchant_id: str | None = None
    payee_email: str | None = None
    payer_country_code: str | None = None
    payment_sources: list[str] = Field(default_factory=list)
    approval_url: str | None = None
    capture_id: str | None = None
    capture_status: str | None = None
    raw_response: dict[str, Any] = Field(default_factory=dict)


class PayPalCaptureResult(BaseModel):
    paypal_order_id: str
    order_status: str
    paypal_capture_id: str | None = None
    capture_status: str | None = None
    amount_value: Decimal | None = None
    currency_code: str | None = None
    raw_response: dict[str, Any] = Field(default_factory=dict)


class PayPalRefundResult(BaseModel):
    paypal_refund_id: str
    paypal_capture_id: str
    status: str
    amount_value: Decimal | None = None
    currency_code: str | None = None
    raw_response: dict[str, Any] = Field(default_factory=dict)


class PayPalWebhookHeaders(BaseModel):
    transmission_id: str
    transmission_time: str
    cert_url: str
    auth_algo: str
    transmission_sig: str

