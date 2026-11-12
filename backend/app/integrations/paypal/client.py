from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PayPalError(RuntimeError):
    """Base exception for PayPal API failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        debug_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.debug_id = debug_id


class PayPalNotConfiguredError(PayPalError):
    """Raised when PayPal credentials are not configured."""


class PayPalClient:
    """Async PayPal REST API v2 client with OAuth2 token caching and auto-refresh."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.paypal_base_url.rstrip("/")
        self._client_id = self.settings.paypal_client_id.strip()
        self._client_secret = self.settings.paypal_client_secret.get_secret_value().strip()
        self.webhook_id = self.settings.paypal_webhook_id.strip()
        self.timeout_seconds = self.settings.paypal_timeout_seconds

        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()
        self._merchant_cache: dict[str, dict[str, Any]] = {}

    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def is_webhook_configured(self) -> bool:
        return bool(self.is_configured() and self.webhook_id)

    def invalidate_token(self) -> None:
        self._access_token = None
        self._token_expires_at = 0.0

    async def get_access_token(self, force_refresh: bool = False) -> str:
        """Obtain a valid PayPal OAuth2 Bearer token, refreshing automatically when needed."""
        if not self.is_configured():
            raise PayPalNotConfiguredError(
                "PayPal credentials (PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET) are not configured."
            )

        now = time.monotonic()
        if not force_refresh and self._access_token and now < self._token_expires_at:
            return self._access_token

        async with self._token_lock:
            now = time.monotonic()
            if not force_refresh and self._access_token and now < self._token_expires_at:
                return self._access_token

            url = f"{self.base_url}/v1/oauth2/token"
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        url,
                        auth=(self._client_id, self._client_secret),
                        headers={"Accept": "application/json"},
                        data={"grant_type": "client_credentials"},
                    )
            except httpx.TimeoutException as exc:
                raise PayPalError("PayPal OAuth2 token request timed out.") from exc
            except httpx.RequestError as exc:
                raise PayPalError(
                    f"PayPal OAuth2 network error: {exc.__class__.__name__}"
                ) from exc

            if response.status_code >= 400:
                debug_id = response.headers.get("paypal-debug-id")
                logger.error(
                    "paypal_oauth_failed",
                    status_code=response.status_code,
                    debug_id=debug_id,
                )
                raise PayPalError(
                    f"PayPal OAuth2 authentication failed with HTTP {response.status_code}.",
                    status_code=response.status_code,
                    debug_id=debug_id,
                )

            data = response.json()
            token = data.get("access_token")
            expires_in = int(data.get("expires_in") or 300)
            if not token:
                raise PayPalError("PayPal OAuth2 response omitted access_token.")

            # Refresh 60s before nominal expiry
            safety_margin = min(60, max(expires_in // 10, 5))
            self._access_token = token
            self._token_expires_at = time.monotonic() + max(1, expires_in - safety_margin)
            logger.info("paypal_oauth_token_acquired", expires_in=expires_in)
            return token

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Perform an authenticated PayPal REST API call with automatic 401 token refresh."""
        token = await self.get_access_token()
        url = f"{self.base_url}{path}"

        for attempt in range(2):
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if idempotency_key:
                headers["PayPal-Request-Id"] = idempotency_key

            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.request(
                        method=method.upper(),
                        url=url,
                        headers=headers,
                        json=json_body,
                    )
            except httpx.TimeoutException as exc:
                raise PayPalError(
                    f"PayPal API timeout on {method.upper()} {path}."
                ) from exc
            except httpx.RequestError as exc:
                raise PayPalError(
                    f"PayPal API network error on {method.upper()} {path}: {exc.__class__.__name__}"
                ) from exc

            if response.status_code == 401 and attempt == 0:
                self.invalidate_token()
                token = await self.get_access_token(force_refresh=True)
                continue

            debug_id = response.headers.get("paypal-debug-id")
            if response.status_code >= 400:
                error_detail = self._extract_error_message(response)
                logger.error(
                    "paypal_api_error",
                    method=method.upper(),
                    path=path,
                    status_code=response.status_code,
                    debug_id=debug_id,
                    detail=error_detail,
                )
                raise PayPalError(
                    f"PayPal API error ({response.status_code}): {error_detail}",
                    status_code=response.status_code,
                    debug_id=debug_id,
                )

            if not response.content:
                return {}
            return response.json()

        raise PayPalError("PayPal API request failed after token refresh.")

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            body = response.json()
            if isinstance(body, dict):
                name = body.get("name") or ""
                message = body.get("message") or ""
                if name or message:
                    return f"{name}: {message}".strip(": ")
        except ValueError:
            pass
        return f"HTTP {response.status_code}"

    async def check_health(self, verify_remote: bool = True) -> dict[str, Any]:
        """Check PayPal integration status safely without leaking secrets."""
        if not self.is_configured():
            return {
                "status": "NOT_CONFIGURED",
                "environment": "sandbox" if "sandbox" in self.base_url else "live",
                "webhook_configured": False,
                "detail": "PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET are not configured.",
            }

        if not verify_remote:
            return {
                "status": "CONFIGURED",
                "environment": "sandbox" if "sandbox" in self.base_url else "live",
                "webhook_configured": self.is_webhook_configured(),
                "detail": "PayPal credentials configured.",
            }

        try:
            await self.get_access_token()
            return {
                "status": "HEALTHY",
                "environment": "sandbox" if "sandbox" in self.base_url else "live",
                "webhook_configured": self.is_webhook_configured(),
                "detail": "PayPal OAuth2 token acquisition verified.",
            }
        except PayPalError as exc:
            return {
                "status": "UNHEALTHY",
                "environment": "sandbox" if "sandbox" in self.base_url else "live",
                "webhook_configured": self.is_webhook_configured(),
                "detail": str(exc),
            }

    async def get_merchant_integration(self, merchant_id: str) -> dict[str, Any] | None:
        """Best-effort cached lookup of PayPal merchant country and receiving readiness."""
        cleaned = (merchant_id or "").strip()
        if not cleaned or not self.is_configured():
            return None
        cached = self._merchant_cache.get(cleaned)
        if cached is not None:
            return cached
        try:
            data = await self.request(
                "GET",
                f"/v1/customer/partners/{cleaned}/merchant-integrations/{cleaned}",
            )
            info = {
                "merchant_id": str(data.get("merchant_id") or cleaned),
                "country": str(data.get("country") or "").strip().upper() or None,
                "payments_receivable": data.get("payments_receivable"),
            }
            self._merchant_cache[cleaned] = info
            return info
        except PayPalError:
            return None

