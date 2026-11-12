from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.observability import observability
from app.core.security import utc_now
from app.utils.currency import (
    CurrencyError,
    quantize_amount,
    quantize_exchange_rate,
    to_decimal,
    validate_currency_code,
)

logger = get_logger(__name__)

_RATE_CACHE: dict[tuple[str, str, str], tuple[float, "ExchangeRateQuote"]] = {}
_RATE_CACHE_LOCK = threading.Lock()
_MAX_CACHE_ENTRIES = 256


class ExchangeRateError(RuntimeError):
    """Raised when live exchange rates cannot be retrieved or validated."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 503,
        base_currency: str | None = None,
        target_currency: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.base_currency = base_currency
        self.target_currency = target_currency


class ExchangeRateQuote(BaseModel):
    base_currency: str
    target_currency: str
    rate: Decimal
    timestamp: datetime
    source: str
    cached: bool = False


class CurrencyConversion(BaseModel):
    original_amount: Decimal
    original_currency: str
    display_amount: Decimal
    display_currency: str
    exchange_rate: Decimal
    exchange_rate_timestamp: datetime
    source: str
    cached: bool = False


def clear_exchange_rate_cache() -> None:
    """Clear in-memory cached FX quotes."""
    with _RATE_CACHE_LOCK:
        _RATE_CACHE.clear()


class ExchangeRateService:
    """Centralized multi-currency exchange-rate lookup, TTL caching, and Decimal conversion."""

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    def _client_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "timeout": float(self.settings.exchange_rate_timeout_seconds),
        }
        if self.transport is not None:
            kwargs["transport"] = self.transport
        return kwargs

    def _build_request(
        self, base: str, target: str
    ) -> tuple[str, dict[str, str], dict[str, str]]:
        raw_base = (self.settings.exchange_rate_base_url or "").strip().rstrip("/")
        if not raw_base:
            raise ExchangeRateError(
                "Exchange-rate service URL is not configured (EXCHANGE_RATE_BASE_URL).",
                status_code=503,
                base_currency=base,
                target_currency=target,
            )

        api_key = self.settings.exchange_rate_api_key.get_secret_value().strip()
        headers: dict[str, str] = {"Accept": "application/json"}
        params: dict[str, str] = {}

        if "{api_key}" in raw_base or "{base}" in raw_base:
            if "{api_key}" in raw_base and not api_key:
                raise ExchangeRateError(
                    "EXCHANGE_RATE_API_KEY is required by the configured exchange-rate endpoint.",
                    status_code=503,
                    base_currency=base,
                    target_currency=target,
                )
            url = raw_base.replace("{api_key}", api_key).replace("{base}", base)
            if "/latest/" not in url and not url.endswith(base):
                url = f"{url}/latest/{base}"
        elif "exchangerate-api.com" in raw_base.lower():
            if not api_key:
                raise ExchangeRateError(
                    "EXCHANGE_RATE_API_KEY is required for ExchangeRate-API.",
                    status_code=503,
                    base_currency=base,
                    target_currency=target,
                )
            url = f"{raw_base}/{api_key}/latest/{base}"
        else:
            url = f"{raw_base}/latest"
            params = {"base": base, "symbols": target}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

        return url, params, headers

    def _extract_rate(
        self, payload: Any, *, base: str, target: str
    ) -> tuple[Decimal, datetime, str]:
        if not isinstance(payload, dict):
            raise ExchangeRateError(
                "Exchange-rate API returned an invalid response payload.",
                base_currency=base,
                target_currency=target,
            )

        if str(payload.get("result") or "").lower() == "error":
            err_type = payload.get("error-type") or payload.get("error") or "unknown error"
            raise ExchangeRateError(
                f"Exchange-rate provider error: {err_type}.",
                base_currency=base,
                target_currency=target,
            )

        rates = payload.get("rates") or payload.get("conversion_rates")
        if not isinstance(rates, dict) or target not in rates:
            raise ExchangeRateError(
                f"Live exchange rate for {base} -> {target} was not included by provider.",
                base_currency=base,
                target_currency=target,
            )

        raw_rate = rates.get(target)
        try:
            rate_dec = quantize_exchange_rate(to_decimal(raw_rate))
        except CurrencyError as exc:
            raise ExchangeRateError(
                f"Invalid exchange rate value returned for {base} -> {target}.",
                base_currency=base,
                target_currency=target,
            ) from exc

        if rate_dec <= Decimal("0"):
            raise ExchangeRateError(
                f"Non-positive exchange rate returned for {base} -> {target}.",
                base_currency=base,
                target_currency=target,
            )

        fetched_at = utc_now()
        source = (self.settings.exchange_rate_base_url or "exchange_rate_api").strip()
        return rate_dec, fetched_at, source

    async def get_rate(self, base_currency: str, target_currency: str) -> ExchangeRateQuote:
        """Fetch live (or TTL-cached) exchange rate from base_currency to target_currency.

        Never falls back to hardcoded exchange rates on upstream failure.
        """
        try:
            base = validate_currency_code(base_currency)
            target = validate_currency_code(target_currency)
        except CurrencyError as exc:
            raise ExchangeRateError(str(exc), status_code=400) from exc

        if base == target:
            return ExchangeRateQuote(
                base_currency=base,
                target_currency=target,
                rate=Decimal("1.000000"),
                timestamp=utc_now(),
                source="identity",
                cached=False,
            )

        ttl = int(self.settings.exchange_rate_cache_ttl_seconds)
        cache_key = (
            (self.settings.exchange_rate_base_url or "").strip().rstrip("/"),
            base,
            target,
        )
        if ttl > 0:
            now_mono = time.monotonic()
            with _RATE_CACHE_LOCK:
                entry = _RATE_CACHE.get(cache_key)
                if entry is not None and (now_mono - entry[0]) < ttl:
                    observability.increment("exchange_rate_cache_hits")
                    return entry[1].model_copy(update={"cached": True})

        url, params, headers = self._build_request(base, target)
        observability.increment("exchange_rate_requests")

        last_exc: Exception | None = None
        response: httpx.Response | None = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(**self._client_kwargs()) as client:
                    response = await client.get(url, params=params or None, headers=headers)
                if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                    await asyncio.sleep(0.25)
                    continue
                break
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt == 0:
                    await asyncio.sleep(0.25)
                    continue

        if response is None:
            observability.increment("exchange_rate_errors")
            raise ExchangeRateError(
                f"Unable to reach live exchange-rate service for {base} -> {target}: {last_exc}",
                status_code=503,
                base_currency=base,
                target_currency=target,
            )

        if response.status_code >= 400:
            observability.increment("exchange_rate_errors")
            raise ExchangeRateError(
                f"Live exchange-rate service returned HTTP {response.status_code} for {base} -> {target}.",
                status_code=503,
                base_currency=base,
                target_currency=target,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            observability.increment("exchange_rate_errors")
            raise ExchangeRateError(
                f"Invalid JSON received from live exchange-rate service for {base} -> {target}.",
                status_code=503,
                base_currency=base,
                target_currency=target,
            ) from exc

        rate_dec, fetched_at, source = self._extract_rate(payload, base=base, target=target)
        quote = ExchangeRateQuote(
            base_currency=base,
            target_currency=target,
            rate=rate_dec,
            timestamp=fetched_at,
            source=source,
            cached=False,
        )

        if ttl > 0:
            with _RATE_CACHE_LOCK:
                if len(_RATE_CACHE) >= _MAX_CACHE_ENTRIES:
                    oldest = min(_RATE_CACHE, key=lambda k: _RATE_CACHE[k][0])
                    _RATE_CACHE.pop(oldest, None)
                _RATE_CACHE[cache_key] = (time.monotonic(), quote)

        return quote

    async def convert_amount(
        self,
        amount: Decimal | str | int,
        from_currency: str,
        to_currency: str,
    ) -> CurrencyConversion:
        """Convert monetary amount from from_currency to to_currency using Decimal precision."""
        try:
            src = validate_currency_code(from_currency)
            dst = validate_currency_code(to_currency)
            original_dec = quantize_amount(
                amount if isinstance(amount, Decimal) else to_decimal(amount, allow_zero=True),
                src,
            )
        except CurrencyError as exc:
            raise ExchangeRateError(str(exc), status_code=400) from exc

        quote = await self.get_rate(src, dst)
        if src == dst:
            display_dec = original_dec
        else:
            display_dec = quantize_amount(original_dec * quote.rate, dst)

        return CurrencyConversion(
            original_amount=original_dec,
            original_currency=src,
            display_amount=display_dec,
            display_currency=dst,
            exchange_rate=quote.rate,
            exchange_rate_timestamp=quote.timestamp,
            source=quote.source,
            cached=quote.cached,
        )

