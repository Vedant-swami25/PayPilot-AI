from __future__ import annotations

from typing import Any, Mapping

from app.integrations.paypal.client import PayPalClient, PayPalError
from app.integrations.paypal.schemas import PayPalWebhookHeaders


class PayPalWebhookVerificationError(PayPalError):
    """Raised when webhook headers or PayPal signature verification fail."""


class PayPalWebhooksAPI:
    """PayPal webhook signature verification via /v1/notifications/verify-webhook-signature."""

    def __init__(self, client: PayPalClient) -> None:
        self.client = client

    @staticmethod
    def extract_headers(headers: Mapping[str, str]) -> PayPalWebhookHeaders:
        """Extract required PayPal transmission headers case-insensitively."""
        lowered = {k.lower(): v for k, v in headers.items()}
        required_map = {
            "transmission_id": "paypal-transmission-id",
            "transmission_time": "paypal-transmission-time",
            "cert_url": "paypal-cert-url",
            "auth_algo": "paypal-auth-algo",
            "transmission_sig": "paypal-transmission-sig",
        }
        missing = [header for header in required_map.values() if not lowered.get(header)]
        if missing:
            raise PayPalWebhookVerificationError(
                f"Missing required PayPal webhook headers: {', '.join(missing)}",
                status_code=400,
            )

        return PayPalWebhookHeaders(
            transmission_id=lowered["paypal-transmission-id"],
            transmission_time=lowered["paypal-transmission-time"],
            cert_url=lowered["paypal-cert-url"],
            auth_algo=lowered["paypal-auth-algo"],
            transmission_sig=lowered["paypal-transmission-sig"],
        )

    async def verify_signature(
        self,
        *,
        headers: Mapping[str, str],
        webhook_event: dict[str, Any],
    ) -> bool:
        """Verify incoming webhook signature against PayPal's official verification endpoint."""
        if not self.client.is_configured() or not self.client.webhook_id:
            raise PayPalWebhookVerificationError(
                "PayPal webhook verification is not configured (PAYPAL_WEBHOOK_ID or credentials missing).",
                status_code=503,
            )

        parsed_headers = self.extract_headers(headers)
        payload = {
            "auth_algo": parsed_headers.auth_algo,
            "cert_url": parsed_headers.cert_url,
            "transmission_id": parsed_headers.transmission_id,
            "transmission_sig": parsed_headers.transmission_sig,
            "transmission_time": parsed_headers.transmission_time,
            "webhook_id": self.client.webhook_id,
            "webhook_event": webhook_event,
        }

        response = await self.client.request(
            "POST",
            "/v1/notifications/verify-webhook-signature",
            json_body=payload,
        )
        status_str = str(response.get("verification_status") or "").upper()
        return status_str == "SUCCESS"

