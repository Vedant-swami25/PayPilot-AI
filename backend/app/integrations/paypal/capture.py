from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.integrations.paypal.client import PayPalClient, PayPalError
from app.integrations.paypal.schemas import PayPalCaptureResult, PayPalRefundResult
from app.utils.currency import format_paypal_amount, to_decimal


class PayPalCaptureAPI:
    """PayPal Orders v2 capture and Payments v2 capture lookup API."""

    def __init__(self, client: PayPalClient) -> None:
        self.client = client

    async def capture_order(
        self,
        *,
        paypal_order_id: str,
        idempotency_key: str,
    ) -> PayPalCaptureResult:
        """Capture funds for an approved PayPal order."""
        data = await self.client.request(
            "POST",
            f"/v2/checkout/orders/{paypal_order_id}/capture",
            json_body={},
            idempotency_key=idempotency_key,
        )

        capture_id: str | None = None
        capture_status: str | None = None
        amount_value: Decimal | None = None
        currency_code: str | None = None

        purchase_units = data.get("purchase_units") or []
        if purchase_units and isinstance(purchase_units[0], dict):
            payments = purchase_units[0].get("payments") or {}
            captures = payments.get("captures") or []
            if captures and isinstance(captures[0], dict):
                cap = captures[0]
                capture_id = cap.get("id")
                capture_status = str(cap.get("status") or "").upper() or None
                amt = cap.get("amount") or {}
                if amt.get("value") is not None:
                    amount_value = to_decimal(amt["value"], allow_zero=True)
                    currency_code = str(amt.get("currency_code") or "").upper() or None

        return PayPalCaptureResult(
            paypal_order_id=str(data.get("id") or paypal_order_id),
            order_status=str(data.get("status") or "UNKNOWN").upper(),
            paypal_capture_id=capture_id,
            capture_status=capture_status,
            amount_value=amount_value,
            currency_code=currency_code,
            raw_response=data,
        )

    async def get_capture_details(self, capture_id: str) -> dict[str, Any]:
        """Retrieve capture details directly from PayPal Payments API v2."""
        return await self.client.request("GET", f"/v2/payments/captures/{capture_id}")

    async def refund_capture(
        self,
        *,
        capture_id: str,
        idempotency_key: str,
        amount: Decimal | None = None,
        currency: str | None = None,
        note_to_payer: str | None = None,
    ) -> PayPalRefundResult:
        """Issue a full (or specified) refund for a completed PayPal capture."""
        body: dict[str, Any] = {}
        if amount is not None and currency is not None:
            body["amount"] = {
                "value": format_paypal_amount(amount, currency),
                "currency_code": currency.upper(),
            }
        if note_to_payer:
            body["note_to_payer"] = note_to_payer[:255]

        data = await self.client.request(
            "POST",
            f"/v2/payments/captures/{capture_id}/refund",
            json_body=body,
            idempotency_key=idempotency_key,
        )
        refund_id = str(data.get("id") or "").strip()
        if not refund_id:
            raise PayPalError("PayPal refund response omitted refund ID.")

        amt = data.get("amount") or {}
        amount_value: Decimal | None = None
        currency_code: str | None = None
        if amt.get("value") is not None:
            amount_value = to_decimal(amt["value"], allow_zero=True)
            currency_code = str(amt.get("currency_code") or "").upper() or None

        return PayPalRefundResult(
            paypal_refund_id=refund_id,
            paypal_capture_id=capture_id,
            status=str(data.get("status") or "UNKNOWN").upper(),
            amount_value=amount_value,
            currency_code=currency_code,
            raw_response=data,
        )

