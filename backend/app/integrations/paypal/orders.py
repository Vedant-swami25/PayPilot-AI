from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.integrations.paypal.client import PayPalClient, PayPalError
from app.integrations.paypal.schemas import (
    PayPalLink,
    PayPalOrderCreateResult,
    PayPalOrderDetails,
)
from app.utils.currency import format_paypal_amount, to_decimal
from app.utils.helpers import truncate_text


def _extract_approval_url(links: list[dict[str, Any]]) -> str | None:
    for preferred_rel in ("payer-action", "approve"):
        for link in links:
            if link.get("rel") == preferred_rel and link.get("href"):
                return str(link["href"])
    return None


class PayPalOrdersAPI:
    """PayPal Orders API v2 operations."""

    def __init__(self, client: PayPalClient) -> None:
        self.client = client

    async def create_order(
        self,
        *,
        reference_id: str,
        amount: Decimal,
        currency: str,
        description: str,
        idempotency_key: str,
        return_url: str,
        cancel_url: str,
    ) -> PayPalOrderCreateResult:
        """Create a PayPal checkout order with intent=CAPTURE."""
        formatted_value = format_paypal_amount(amount, currency)
        payload: dict[str, Any] = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": reference_id[:256],
                    "description": truncate_text(description, 127) or "PayPilot AI Order",
                    "amount": {
                        "currency_code": currency.upper(),
                        "value": formatted_value,
                    },
                }
            ],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                        "user_action": "PAY_NOW",
                    }
                }
            },
        }

        data = await self.client.request(
            "POST",
            "/v2/checkout/orders",
            json_body=payload,
            idempotency_key=idempotency_key,
        )

        paypal_order_id = str(data.get("id") or "").strip()
        if not paypal_order_id:
            raise PayPalError("PayPal create order response did not include an order ID.")

        raw_links = data.get("links") or []
        links = [PayPalLink.model_validate(item) for item in raw_links if isinstance(item, dict)]
        approval_url = _extract_approval_url(raw_links)

        return PayPalOrderCreateResult(
            paypal_order_id=paypal_order_id,
            status=str(data.get("status") or "CREATED").upper(),
            approval_url=approval_url,
            links=links,
            raw_response=data,
        )

    async def get_order(self, paypal_order_id: str) -> PayPalOrderDetails:
        """Retrieve authoritative order details directly from PayPal."""
        data = await self.client.request("GET", f"/v2/checkout/orders/{paypal_order_id}")

        purchase_units = data.get("purchase_units") or []
        amount_value: Decimal | None = None
        currency_code: str | None = None
        payee_merchant_id: str | None = None
        payee_email: str | None = None
        capture_id: str | None = None
        capture_status: str | None = None

        if purchase_units and isinstance(purchase_units[0], dict):
            pu = purchase_units[0]
            amount_block = pu.get("amount") or {}
            if amount_block.get("value") is not None:
                amount_value = to_decimal(amount_block["value"], allow_zero=True)
                currency_code = str(amount_block.get("currency_code") or "").upper() or None

            payee_block = pu.get("payee") or {}
            if isinstance(payee_block, dict):
                payee_merchant_id = str(payee_block.get("merchant_id") or "").strip() or None
                payee_email = str(payee_block.get("email_address") or "").strip() or None

            payments = pu.get("payments") or {}
            captures = payments.get("captures") or []
            if captures and isinstance(captures[0], dict):
                capture_id = captures[0].get("id")
                capture_status = captures[0].get("status")

        payer_block = data.get("payer") or {}
        payer_address = payer_block.get("address") if isinstance(payer_block, dict) else {}
        payer_country_code = (
            str(payer_address.get("country_code") or "").strip().upper() or None
            if isinstance(payer_address, dict)
            else None
        )
        raw_sources = data.get("payment_source") or {}
        payment_sources = (
            sorted(str(k) for k in raw_sources.keys())
            if isinstance(raw_sources, dict)
            else []
        )

        raw_links = data.get("links") or []
        return PayPalOrderDetails(
            paypal_order_id=str(data.get("id") or paypal_order_id),
            status=str(data.get("status") or "UNKNOWN").upper(),
            intent=data.get("intent"),
            amount_value=amount_value,
            currency_code=currency_code,
            payee_merchant_id=payee_merchant_id,
            payee_email=payee_email,
            payer_country_code=payer_country_code,
            payment_sources=payment_sources,
            approval_url=_extract_approval_url(raw_links),
            capture_id=capture_id,
            capture_status=capture_status,
            raw_response=data,
        )

