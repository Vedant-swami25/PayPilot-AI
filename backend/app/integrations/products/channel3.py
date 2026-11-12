from __future__ import annotations

import asyncio
import random
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.observability import observability
from app.integrations.products.provider import (
    MerchantDetails,
    ProductProvider,
    ProductSearchResult,
    ProviderProduct,
    ProviderUnavailableError,
)
from app.utils.currency import CurrencyError, quantize_amount, to_decimal, validate_currency_code

logger = get_logger(__name__)


class Channel3ProductProvider(ProductProvider):
    """Channel3 product discovery integration using official REST API."""

    provider_name = "channel3"

    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        self._api_key = cfg.channel3_api_key.get_secret_value().strip()
        self.base_url = cfg.channel3_base_url.strip().rstrip("/")
        self.timeout_seconds = 15.0

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _clean_str(value: Any) -> str | None:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return None

    @classmethod
    def _parse_price_block(
        cls, price_block: Any, fallback_currency: Any = None
    ) -> tuple[Decimal, str] | None:
        """Parse monetary price and ISO currency from Channel3 dict or scalar shapes."""
        raw_price: Any = None
        raw_currency: Any = fallback_currency

        if isinstance(price_block, dict):
            for key in ("price", "amount", "value"):
                if price_block.get(key) is not None:
                    raw_price = price_block.get(key)
                    break
            if price_block.get("currency") is not None:
                raw_currency = price_block.get("currency")
        elif price_block is not None and not isinstance(price_block, (bool, list)):
            raw_price = price_block

        if raw_price is None:
            return None

        currency_str = cls._clean_str(raw_currency) or "USD"
        try:
            currency = validate_currency_code(currency_str)
            price = quantize_amount(to_decimal(raw_price), currency)
            return price, currency
        except CurrencyError:
            return None

    @classmethod
    def _normalize_availability(cls, raw_value: Any) -> str:
        """Normalize Schema.org / Channel3 availability strings to internal constants."""
        cleaned = cls._clean_str(raw_value)
        if not cleaned:
            return "UNKNOWN"
        if cleaned.lower().startswith(("http://", "https://")) and "/" in cleaned:
            cleaned = cleaned.rsplit("/", 1)[-1].strip()
        canonical = "".join(ch for ch in cleaned.lower() if ch.isalnum())
        mapping = {
            "instock": "IN_STOCK",
            "outofstock": "OUT_OF_STOCK",
            "soldout": "OUT_OF_STOCK",
            "preorder": "PRE_ORDER",
            "backorder": "BACKORDER",
            "limitedavailability": "LIMITED_AVAILABILITY",
            "instoreonly": "IN_STORE_ONLY",
            "discontinued": "DISCONTINUED",
        }
        if canonical in mapping:
            return mapping[canonical]
        return cleaned.upper().replace(" ", "_")

    @classmethod
    def _extract_brand(cls, item: dict[str, Any]) -> str | None:
        """Extract brand name from Channel3 v1 `brands` list or legacy fields."""
        brands = item.get("brands")
        if isinstance(brands, list):
            for entry in brands:
                if isinstance(entry, dict):
                    name = cls._clean_str(entry.get("name"))
                    if name:
                        return name
                else:
                    name = cls._clean_str(entry)
                    if name:
                        return name

        for key in ("brand_name", "brand"):
            val = item.get(key)
            if isinstance(val, dict):
                name = cls._clean_str(val.get("name"))
                if name:
                    return name
            else:
                name = cls._clean_str(val)
                if name:
                    return name
        return None

    @classmethod
    def _extract_image_url(cls, item: dict[str, Any]) -> str | None:
        """Extract primary image URL from Channel3 v1 `images` dicts or legacy strings."""
        direct = cls._clean_str(item.get("image_url"))
        if direct:
            return direct

        for key in ("images", "image_urls"):
            raw_images = item.get(key)
            if not isinstance(raw_images, list):
                continue
            first_url: str | None = None
            for entry in raw_images:
                if isinstance(entry, dict):
                    candidate = cls._clean_str(entry.get("url")) or cls._clean_str(
                        entry.get("cleaned_url")
                    )
                    if candidate:
                        if entry.get("is_main_image") is True:
                            return candidate
                        if first_url is None:
                            first_url = candidate
                else:
                    candidate = cls._clean_str(entry)
                    if candidate and first_url is None:
                        first_url = candidate
            if first_url:
                return first_url
        return None

    @classmethod
    def _extract_category(cls, item: dict[str, Any]) -> str | None:
        """Extract human-readable category from v1 dict or legacy string/list."""
        cat = item.get("category")
        if isinstance(cat, dict):
            return cls._clean_str(cat.get("title")) or cls._clean_str(cat.get("slug"))
        direct = cls._clean_str(cat)
        if direct:
            return direct

        cats = item.get("categories")
        if isinstance(cats, list):
            for entry in cats:
                if isinstance(entry, dict):
                    name = cls._clean_str(entry.get("title")) or cls._clean_str(entry.get("slug"))
                    if name:
                        return name
                else:
                    name = cls._clean_str(entry)
                    if name:
                        return name
        return None

    def _select_primary_offer(
        self, item: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, tuple[Decimal, str] | None]:
        """Select the best valid offer and its parsed (price, currency) from v1 `offers`."""
        raw_offers = item.get("offers")
        if not isinstance(raw_offers, list):
            return None, None

        first_valid_offer: tuple[dict[str, Any], tuple[Decimal, str]] | None = None
        fallback_offer_dict: dict[str, Any] | None = None

        for offer in raw_offers:
            if not isinstance(offer, dict):
                continue
            if fallback_offer_dict is None:
                fallback_offer_dict = offer

            offer_currency = offer.get("currency") or item.get("currency")
            price_source = offer.get("price")
            if price_source is None:
                for key in ("amount", "value"):
                    if offer.get(key) is not None:
                        price_source = offer.get(key)
                        break

            parsed = self._parse_price_block(price_source, fallback_currency=offer_currency)
            if parsed is None:
                continue

            if self._normalize_availability(offer.get("availability")) == "IN_STOCK":
                return offer, parsed
            if first_valid_offer is None:
                first_valid_offer = (offer, parsed)

        if first_valid_offer is not None:
            return first_valid_offer
        return fallback_offer_dict, None

    def _normalize_product(self, item: Any) -> ProviderProduct | None:
        """Map Channel3 v1 and legacy product schemas to internal ProviderProduct safely."""
        if not isinstance(item, dict):
            return None

        ext_id = self._clean_str(item.get("id")) or self._clean_str(item.get("product_id"))
        name = self._clean_str(item.get("title")) or self._clean_str(item.get("name"))
        if not ext_id or not name:
            return None

        primary_offer, parsed_price = self._select_primary_offer(item)
        if parsed_price is None:
            parsed_price = self._parse_price_block(
                item.get("price"), fallback_currency=item.get("currency")
            )
        if parsed_price is None:
            return None

        price, currency = parsed_price

        offer_domain = self._clean_str(primary_offer.get("domain")) if primary_offer else None
        brand_name = self._extract_brand(item)

        merchant_raw = item.get("merchant") or item.get("seller")
        merchant_url: str | None = None
        merchant_name: str | None = None

        if isinstance(merchant_raw, dict):
            merchant_name = self._clean_str(merchant_raw.get("name"))
            merchant_url = self._clean_str(merchant_raw.get("url"))
        else:
            merchant_name = self._clean_str(merchant_raw)

        if not merchant_name:
            merchant_name = offer_domain or brand_name or "Unknown Merchant"

        raw_availability = (
            primary_offer.get("availability") if primary_offer else None
        ) or item.get("availability")
        availability = self._normalize_availability(raw_availability)

        image_url = self._extract_image_url(item)
        product_url = (
            self._clean_str(item.get("url"))
            or self._clean_str(item.get("product_url"))
            or (self._clean_str(primary_offer.get("url")) if primary_offer else None)
        )

        raw_specs = item.get("specifications") or item.get("attributes")
        specs: dict[str, Any] = dict(raw_specs) if isinstance(raw_specs, dict) else {}
        if brand_name:
            specs.setdefault("brand", brand_name)
        if offer_domain:
            specs.setdefault("domain", offer_domain)
        if isinstance(item.get("ratings"), dict) and item["ratings"]:
            specs.setdefault("ratings", item["ratings"])
        if isinstance(item.get("key_features"), list) and item["key_features"]:
            specs.setdefault("key_features", item["key_features"])
        if isinstance(item.get("materials"), list) and item["materials"]:
            specs.setdefault("materials", item["materials"])
        if isinstance(item.get("structured_attributes"), dict) and item["structured_attributes"]:
            specs.setdefault("structured_attributes", item["structured_attributes"])
        if item.get("categories"):
            specs["categories"] = item["categories"]
        if isinstance(item.get("variants"), list):
            specs["variant_count"] = len(item["variants"])

        return ProviderProduct(
            external_product_id=ext_id,
            name=name,
            description=self._clean_str(item.get("description")),
            price=price,
            currency=currency,
            merchant=merchant_name,
            merchant_details=MerchantDetails(
                name=merchant_name,
                url=merchant_url,
                verified=bool(item.get("verified_merchant", False)),
            ),
            availability=availability,
            image_url=image_url,
            product_url=product_url,
            category=self._extract_category(item),
            specifications=specs,
            provider=self.provider_name,
            is_test_data=False,
        )

    async def search_products(
        self,
        query: str,
        *,
        max_price: Decimal | None = None,
        currency: str = "USD",
        limit: int = 10,
    ) -> ProductSearchResult:
        if not self.is_configured():
            return ProductSearchResult(
                query=query,
                provider=self.provider_name,
                provider_status="NOT_CONFIGURED",
                is_test_data=False,
                products=[],
                message=(
                    "Channel3 product discovery API key (CHANNEL3_API_KEY) is not configured. "
                    "No products were fabricated."
                ),
            )

        target_currency = currency.upper()
        payload: dict[str, Any] = {
            "query": query,
            "limit": min(max(limit, 1), 30),
        }
        # Channel3 offers are priced in their native merchant currency (typically USD).
        # Only forward the provider max_price filter when the requested currency is USD
        # so an INR/non-USD budget figure is never misinterpreted as USD.
        if max_price is not None and target_currency == "USD":
            price_filter = {"price": {"max_price": float(max_price)}}
            if self.base_url.rstrip("/").endswith("/v0"):
                payload["config"] = {"filters": price_filter}
            else:
                payload["filters"] = price_filter

        observability.increment("channel3_searches")
        products: list[ProviderProduct] = []
        seen_ids: set[str] = set()
        page_token: str | None = None
        max_pages = 2

        for _page in range(max_pages):
            request_payload = dict(payload)
            if page_token:
                request_payload["page_token"] = page_token

            response = await self._post_with_retries(f"{self.base_url}/search", request_payload, query)
            raw_data = response.json()
            next_token: str | None = None

            if isinstance(raw_data, list):
                raw_items = raw_data
            elif isinstance(raw_data, dict):
                candidate_items = (
                    raw_data.get("products")
                    or raw_data.get("results")
                    or raw_data.get("items")
                    or []
                )
                raw_items = candidate_items if isinstance(candidate_items, list) else []
                raw_next = raw_data.get("next_page_token")
                if isinstance(raw_next, str) and raw_next.strip():
                    next_token = raw_next.strip()
            else:
                raw_items = []

            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                normalized = self._normalize_product(item)
                if normalized is None:
                    continue
                if normalized.external_product_id in seen_ids:
                    continue
                # Preserve original merchant price/currency; only enforce numeric max_price
                # when both product price and requested filter share the same currency.
                if (
                    max_price is not None
                    and normalized.currency == target_currency
                    and normalized.price > max_price
                ):
                    continue
                seen_ids.add(normalized.external_product_id)
                products.append(normalized)
                if len(products) >= limit:
                    break

            if len(products) >= limit or not next_token:
                break
            page_token = next_token

        if not products:
            return ProductSearchResult(
                query=query,
                provider=self.provider_name,
                provider_status="NO_RESULTS",
                is_test_data=False,
                products=[],
                message=f"No matching products found for '{query}'.",
            )

        returned_currencies = sorted({p.currency for p in products})
        note: str | None = None
        if max_price is not None and target_currency not in returned_currencies:
            note = (
                f"Showing original merchant prices ({', '.join(returned_currencies)}). "
                f"Max budget in {target_currency} was not applied because listings are priced in {', '.join(returned_currencies)}."
            )

        return ProductSearchResult(
            query=query,
            provider=self.provider_name,
            provider_status="AVAILABLE",
            is_test_data=False,
            products=products,
            message=note,
        )

    async def _post_with_retries(
        self, url: str, payload: dict[str, Any], query: str, max_retries: int = 2
    ) -> httpx.Response:
        last_error: ProviderUnavailableError | None = None
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        url,
                        headers=self._headers(),
                        json=payload,
                    )
            except httpx.TimeoutException as exc:
                observability.increment("channel3_errors")
                last_error = ProviderUnavailableError("Channel3 product search timed out.")
                logger.warning("channel3_search_timeout", query=query, attempt=attempt + 1)
                if attempt < max_retries:
                    await asyncio.sleep(round(0.4 * (2**attempt) * random.uniform(0.5, 1.5), 3))
                    continue
                raise last_error from exc
            except httpx.RequestError as exc:
                observability.increment("channel3_errors")
                last_error = ProviderUnavailableError(
                    f"Channel3 product search network error: {exc.__class__.__name__}"
                )
                logger.warning(
                    "channel3_search_network_error",
                    error=exc.__class__.__name__,
                    attempt=attempt + 1,
                )
                if attempt < max_retries:
                    await asyncio.sleep(round(0.4 * (2**attempt) * random.uniform(0.5, 1.5), 3))
                    continue
                raise last_error from exc

            if response.status_code == 429:
                observability.increment("channel3_rate_limited")
            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = ProviderUnavailableError(
                    f"Channel3 API returned HTTP {response.status_code}."
                )
                if attempt < max_retries:
                    retry_hdr = response.headers.get("retry-after")
                    delay = round(0.4 * (2**attempt) * random.uniform(0.5, 1.5), 3)
                    if retry_hdr:
                        try:
                            delay = min(max(float(retry_hdr), 0.1), 3.0)
                        except ValueError:
                            pass
                    await asyncio.sleep(delay)
                    continue
                observability.increment("channel3_errors")
                raise last_error

            if response.status_code >= 400:
                observability.increment("channel3_errors")
                logger.error("channel3_search_http_error", status_code=response.status_code)
                raise ProviderUnavailableError(
                    f"Channel3 API returned HTTP {response.status_code}."
                )
            return response

        raise last_error or ProviderUnavailableError("Channel3 product search failed.")

    async def get_product_details(
        self, external_product_id: str
    ) -> ProviderProduct | None:
        if not self.is_configured():
            return None

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    f"{self.base_url}/products/{external_product_id}",
                    headers=self._headers(),
                )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise ProviderUnavailableError(
                f"Channel3 product details lookup failed: {exc.__class__.__name__}"
            ) from exc

        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise ProviderUnavailableError(
                f"Channel3 product details returned HTTP {response.status_code}."
            )

        item = response.json()
        if not isinstance(item, dict):
            return None
        if isinstance(item.get("product"), dict) and not (
            item.get("id") or item.get("product_id")
        ):
            item = item["product"]
        return self._normalize_product(item)

