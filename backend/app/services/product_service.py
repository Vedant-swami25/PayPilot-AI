from __future__ import annotations

import threading
import time
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.observability import observability
from app.integrations.products.provider import (
    ProductProvider,
    ProductSearchResult,
    ProviderProduct,
    ProviderUnavailableError,
    get_product_provider,
)
from app.models.product import Product
from app.schemas.product import (
    ProductCompareRequest,
    ProductComparisonItem,
    ProductComparisonResponse,
    ProductResponse,
    ProductSearchResponse,
)
from app.services.exchange_rate import (
    CurrencyConversion,
    ExchangeRateError,
    ExchangeRateService,
)
from app.utils.currency import CurrencyError, quantize_amount, validate_currency_code


_SEARCH_CACHE: dict[tuple[str, str, str, str, int], tuple[float, ProductSearchResult]] = {}
_SEARCH_CACHE_LOCK = threading.Lock()
_MAX_CACHE_ENTRIES = 256


def clear_product_cache() -> None:
    """Clear in-memory product discovery cache."""
    with _SEARCH_CACHE_LOCK:
        _SEARCH_CACHE.clear()


class ProductService:
    """Product search, persistence, and deterministic comparison service."""

    def __init__(
        self,
        settings: Settings | None = None,
        provider: ProductProvider | None = None,
        exchange_rate_service: ExchangeRateService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or get_product_provider(self.settings)
        self.exchange_rate_service = exchange_rate_service or ExchangeRateService(
            self.settings
        )

    async def _convert_or_raise(
        self, amount: Decimal, from_currency: str, to_currency: str
    ) -> CurrencyConversion:
        try:
            return await self.exchange_rate_service.convert_amount(
                amount, from_currency, to_currency
            )
        except ExchangeRateError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=str(exc),
            ) from exc

    async def to_product_response(
        self, product: Product, *, target_currency: str | None = None
    ) -> ProductResponse:
        """Build a ProductResponse preserving original price/currency alongside converted display values."""
        try:
            orig_currency = validate_currency_code(product.currency)
            disp_currency = (
                validate_currency_code(target_currency)
                if target_currency
                else orig_currency
            )
        except CurrencyError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        orig_price = quantize_amount(product.price, orig_currency)
        conv = await self._convert_or_raise(orig_price, orig_currency, disp_currency)
        base = ProductResponse.model_validate(product)
        return base.model_copy(
            update={
                "price": orig_price,
                "currency": orig_currency,
                "original_price": orig_price,
                "original_currency": orig_currency,
                "display_price": conv.display_amount,
                "display_currency": conv.display_currency,
                "exchange_rate": conv.exchange_rate,
                "exchange_rate_timestamp": conv.exchange_rate_timestamp,
            }
        )

    async def upsert_provider_product(
        self, session: AsyncSession, item: ProviderProduct
    ) -> Product:
        """Persist or refresh a verified external product record."""
        result = await session.execute(
            select(Product).where(
                Product.external_product_id == item.external_product_id
            )
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            product = Product(
                external_product_id=item.external_product_id,
                name=item.name,
                description=item.description,
                image_url=item.image_url,
                price=quantize_amount(item.price, item.currency),
                currency=item.currency,
                merchant=item.merchant,
                product_url=item.product_url,
                availability=item.availability,
                category=item.category,
                specifications=item.specifications,
                provider=item.provider,
                is_test_data=item.is_test_data,
            )
            try:
                async with session.begin_nested():
                    session.add(product)
                    await session.flush()
                return product
            except IntegrityError:
                retry_res = await session.execute(
                    select(Product).where(
                        Product.external_product_id == item.external_product_id
                    )
                )
                existing = retry_res.scalar_one_or_none()
                if existing is None:
                    raise

        existing.name = item.name
        existing.description = item.description
        existing.image_url = item.image_url
        existing.price = quantize_amount(item.price, item.currency)
        existing.currency = item.currency
        existing.merchant = item.merchant
        existing.product_url = item.product_url
        existing.availability = item.availability
        existing.category = item.category
        existing.specifications = item.specifications
        existing.provider = item.provider
        existing.is_test_data = item.is_test_data
        await session.flush()
        return existing

    async def search_products(
        self,
        session: AsyncSession,
        *,
        query: str,
        max_price: Decimal | None = None,
        currency: str = "USD",
        limit: int = 10,
    ) -> ProductSearchResponse:
        try:
            normalized_currency = validate_currency_code(currency)
        except CurrencyError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        budget_in_target: Decimal | None = (
            quantize_amount(max_price, normalized_currency)
            if max_price is not None
            else None
        )
        provider_max_price = budget_in_target
        provider_currency = normalized_currency

        if budget_in_target is not None and normalized_currency != "USD":
            usd_budget_conv = await self._convert_or_raise(
                budget_in_target, normalized_currency, "USD"
            )
            provider_max_price = usd_budget_conv.display_amount
            provider_currency = "USD"

        ttl = self.settings.product_cache_ttl_seconds
        cache_key = (
            self.provider.provider_name,
            " ".join(query.strip().lower().split()),
            str(provider_max_price) if provider_max_price is not None else "",
            provider_currency,
            limit,
        )

        search_result: ProductSearchResult | None = None
        if ttl > 0:
            now = time.monotonic()
            with _SEARCH_CACHE_LOCK:
                cached = _SEARCH_CACHE.get(cache_key)
                if cached and (now - cached[0]) < ttl:
                    search_result = cached[1]
                    observability.increment("product_cache_hits")

        if search_result is None:
            try:
                search_result = await self.provider.search_products(
                    query,
                    max_price=provider_max_price,
                    currency=provider_currency,
                    limit=limit,
                )
            except ProviderUnavailableError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(exc),
                ) from exc

            if ttl > 0 and search_result.provider_status == "AVAILABLE" and search_result.products:
                with _SEARCH_CACHE_LOCK:
                    if len(_SEARCH_CACHE) >= _MAX_CACHE_ENTRIES:
                        oldest_key = min(_SEARCH_CACHE, key=lambda k: _SEARCH_CACHE[k][0])
                        _SEARCH_CACHE.pop(oldest_key, None)
                    _SEARCH_CACHE[cache_key] = (time.monotonic(), search_result)

        persisted: list[ProductResponse] = []
        seen_ext_ids: set[str] = set()
        committed_needed = False
        for item in search_result.products:
            if item.external_product_id in seen_ext_ids:
                continue
            seen_ext_ids.add(item.external_product_id)
            product = await self.upsert_provider_product(session, item)
            committed_needed = True
            converted_resp = await self.to_product_response(
                product, target_currency=normalized_currency
            )
            if (
                budget_in_target is not None
                and converted_resp.display_price is not None
                and converted_resp.display_price > budget_in_target
            ):
                continue
            persisted.append(converted_resp)

        if committed_needed:
            await session.commit()

        final_status = search_result.provider_status
        final_message = search_result.message
        if search_result.products and not persisted and budget_in_target is not None:
            final_status = "NO_RESULTS"
            final_message = (
                f"No matching products found within budget of "
                f"{budget_in_target} {normalized_currency}."
            )

        sample_rate = persisted[0].exchange_rate if persisted else None
        sample_ts = persisted[0].exchange_rate_timestamp if persisted else None

        return ProductSearchResponse(
            query=search_result.query,
            provider=search_result.provider,
            is_test_data=search_result.is_test_data,
            provider_status=final_status,
            total=len(persisted),
            products=persisted,
            message=final_message,
            display_currency=normalized_currency,
            exchange_rate=sample_rate,
            exchange_rate_timestamp=sample_ts,
        )

    async def get_product(
        self, session: AsyncSession, product_id: str
    ) -> Product:
        result = await session.execute(
            select(Product).where(
                or_(
                    Product.id == product_id,
                    Product.external_product_id == product_id,
                )
            )
        )
        product = result.scalar_one_or_none()
        if product is not None:
            return product

        try:
            remote = await self.provider.get_product_details(product_id)
        except ProviderUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

        if remote is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product '{product_id}' was not found.",
            )

        persisted = await self.upsert_provider_product(session, remote)
        await session.commit()
        return persisted

    def compare_product_records(
        self,
        products: list[Product],
        *,
        budget: Decimal | None = None,
        requirements: list[str] | None = None,
        target_currency: str | None = None,
        conversions: dict[str, CurrencyConversion] | None = None,
    ) -> ProductComparisonResponse:
        """Execute deterministic numerical and specification comparison across persisted products."""
        if len(products) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least 2 distinct products are required for comparison.",
            )

        if conversions is None:
            currencies = {p.currency for p in products}
            if len(currencies) > 1 or (
                target_currency and validate_currency_code(target_currency) not in currencies
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Currency conversion required to compare products across currencies: {sorted(currencies)}.",
                )

        currency = (
            validate_currency_code(target_currency)
            if target_currency
            else products[0].currency
        )
        prices = [
            quantize_amount(conversions[p.id].display_amount, currency)
            if conversions and p.id in conversions
            else quantize_amount(p.price, currency)
            for p in products
        ]
        lowest_price = min(prices)
        highest_price = max(prices)
        average_price = quantize_amount(
            sum(prices, Decimal("0.00")) / Decimal(len(prices)), currency
        )
        price_spread = quantize_amount(highest_price - lowest_price, currency)

        req_terms = [r.strip().lower() for r in (requirements or []) if r.strip()]
        items: list[ProductComparisonItem] = []

        best_id: str | None = None
        best_rank_tuple: tuple[int, int, Decimal, Decimal] | None = None

        for product in products:
            conv = conversions.get(product.id) if conversions else None
            orig_currency = validate_currency_code(product.currency)
            orig_price = quantize_amount(product.price, orig_currency)
            price = (
                quantize_amount(conv.display_amount, currency)
                if conv is not None
                else quantize_amount(product.price, currency)
            )
            delta = quantize_amount(price - lowest_price, currency)
            if lowest_price > Decimal("0"):
                delta_pct = ((delta / lowest_price) * Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            else:
                delta_pct = Decimal("0.00")

            budget_q = quantize_amount(budget, currency) if budget is not None else None
            within_budget = (price <= budget_q) if budget_q is not None else None

            specs = product.specifications or {}
            searchable = " ".join(
                [
                    product.name,
                    product.description or "",
                    product.category or "",
                    " ".join(f"{k} {v}" for k, v in specs.items()),
                ]
            ).lower()

            if req_terms:
                hits = sum(1 for term in req_terms if term in searchable)
                match_score = (
                    (Decimal(hits) / Decimal(len(req_terms))) * Decimal("100")
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                match_score = Decimal("100.00")

            pros: list[str] = []
            cons: list[str] = []
            if price == lowest_price:
                pros.append(f"Lowest price in comparison ({price} {currency})")
            else:
                pros_delta = f"{delta} {currency} ({delta_pct}%) above lowest option"
                cons.append(pros_delta)

            if within_budget is True:
                pros.append(f"Within budget of {budget_q} {currency}")
            elif within_budget is False:
                cons.append(f"Exceeds budget of {budget_q} {currency}")

            if product.availability.upper() == "IN_STOCK":
                pros.append("Currently in stock")
            else:
                cons.append(f"Availability is {product.availability}")

            if product.is_test_data:
                cons.append("Marked as TEST DATA (non-live inventory)")

            items.append(
                ProductComparisonItem(
                    product_id=product.id,
                    external_product_id=product.external_product_id,
                    name=product.name,
                    merchant=product.merchant,
                    price=price,
                    currency=currency,
                    original_price=orig_price,
                    original_currency=orig_currency,
                    display_price=price,
                    display_currency=currency,
                    exchange_rate=conv.exchange_rate if conv else Decimal("1.000000"),
                    exchange_rate_timestamp=conv.exchange_rate_timestamp if conv else None,
                    availability=product.availability,
                    price_delta_from_lowest=delta,
                    price_delta_percent=delta_pct,
                    within_budget=within_budget,
                    requirement_match_score=match_score,
                    pros=pros,
                    cons=cons,
                    specifications=specs,
                )
            )

            # Deterministic preference: in stock > within budget > highest match score > lowest price
            in_stock_rank = 1 if product.availability.upper() == "IN_STOCK" else 0
            budget_rank = 1 if within_budget is not False else 0
            rank_tuple = (in_stock_rank, budget_rank, match_score, -price)
            if best_rank_tuple is None or rank_tuple > best_rank_tuple:
                best_rank_tuple = rank_tuple
                best_id = product.id

        summary = (
            f"Compared {len(products)} products in {currency}. "
            f"Prices range from {lowest_price} to {highest_price} {currency} "
            f"(average {average_price} {currency})."
        )
        first_conv = next(iter(conversions.values()), None) if conversions else None
        return ProductComparisonResponse(
            currency=currency,
            lowest_price=lowest_price,
            highest_price=highest_price,
            average_price=average_price,
            price_spread=price_spread,
            best_value_product_id=best_id,
            items=items,
            summary=summary,
            exchange_rate=first_conv.exchange_rate if first_conv else None,
            exchange_rate_timestamp=first_conv.exchange_rate_timestamp if first_conv else None,
        )

    async def compare_product_records_async(
        self,
        products: list[Product],
        *,
        budget: Decimal | None = None,
        target_currency: str | None = None,
        requirements: list[str] | None = None,
    ) -> ProductComparisonResponse:
        """Convert product prices into a consistent target currency and run deterministic comparison."""
        if len(products) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least 2 distinct products are required for comparison.",
            )
        try:
            dst_currency = validate_currency_code(target_currency or products[0].currency)
        except CurrencyError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        conversions: dict[str, CurrencyConversion] = {}
        for product in products:
            conversions[product.id] = await self._convert_or_raise(
                product.price, product.currency, dst_currency
            )

        return self.compare_product_records(
            products,
            budget=budget,
            requirements=requirements,
            target_currency=dst_currency,
            conversions=conversions,
        )

    async def compare_products(
        self, session: AsyncSession, payload: ProductCompareRequest
    ) -> ProductComparisonResponse:
        unique_ids = list(dict.fromkeys(payload.product_ids))
        products = [await self.get_product(session, pid) for pid in unique_ids]
        return await self.compare_product_records_async(
            products,
            budget=payload.budget,
            target_currency=payload.currency,
            requirements=payload.requirements,
        )

