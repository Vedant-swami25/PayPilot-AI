from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.security_agent import SecurityAgent
from app.core.config import clear_settings_cache, get_settings
from app.models.product import Product
from app.models.user import SpendingLimit, User
from app.services.exchange_rate import ExchangeRateError, ExchangeRateService
from tests.conftest import register_and_login


_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _patch_httpx_for_fx_and_external(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rates_map: dict[tuple[str, str], float] | None = None,
    fx_status: int = 200,
    fx_calls: list[str] | None = None,
    channel3_products: list[dict] | None = None,
    paypal_bodies: list[dict] | None = None,
) -> dict[str, Any]:
    """Intercept Frankfurter FX, Channel3 v1, and PayPal Sandbox HTTP requests cleanly."""
    state: dict[str, Any] = {"fx_status": fx_status}
    rates = (
        rates_map
        if rates_map is not None
        else {("USD", "INR"): 86.73, ("INR", "USD"): 0.01153, ("EUR", "INR"): 92.00}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        if "frankfurter" in url:
            if fx_calls is not None:
                fx_calls.append(url)
            if state["fx_status"] >= 400:
                return httpx.Response(state["fx_status"], json={"message": "upstream unavailable"})
            base = (request.url.params.get("base") or "USD").upper()
            symbols = (request.url.params.get("symbols") or "INR").upper()
            rate = rates.get((base, symbols))
            if rate is None:
                return httpx.Response(200, json={"base": base, "rates": {}})
            return httpx.Response(
                200,
                json={
                    "amount": 1.0,
                    "base": base,
                    "date": "2026-11-12",
                    "rates": {symbols: rate},
                },
            )

        if "trychannel3.com" in url:
            return httpx.Response(
                200,
                json={
                    "products": channel3_products or [],
                    "next_page_token": None,
                },
            )

        if "paypal.com" in url:
            if url.endswith("/v1/oauth2/token"):
                return httpx.Response(
                    200, json={"access_token": "tok_fx_test", "expires_in": 3600}
                )
            if url.endswith("/v2/checkout/orders") and request.method == "POST":
                body = json.loads(request.content.decode("utf-8"))
                if paypal_bodies is not None:
                    paypal_bodies.append(body)
                return httpx.Response(
                    201,
                    json={
                        "id": f"PP-FX-{len(paypal_bodies or [1])}",
                        "status": "PAYER_ACTION_REQUIRED",
                        "links": [
                            {
                                "rel": "payer-action",
                                "href": "https://sandbox.paypal.com/approve/fx",
                            }
                        ],
                    },
                )

        return httpx.Response(404, json={"detail": f"Unhandled URL in test mock: {url}"})

    transport = httpx.MockTransport(handler)

    class PatchedAsyncClient(_REAL_ASYNC_CLIENT):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", PatchedAsyncClient)
    return state


@pytest.mark.asyncio
async def test_exchange_rate_usd_inr_conversion_and_caching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx_calls: list[str] = []
    _patch_httpx_for_fx_and_external(monkeypatch, fx_calls=fx_calls)
    svc = ExchangeRateService(get_settings())

    # 1. USD -> INR conversion with Decimal accuracy
    usd_to_inr = await svc.convert_amount(Decimal("26.52"), "USD", "INR")
    assert usd_to_inr.original_amount == Decimal("26.52")
    assert usd_to_inr.original_currency == "USD"
    assert usd_to_inr.display_amount == Decimal("2300.08")
    assert usd_to_inr.display_currency == "INR"
    assert usd_to_inr.exchange_rate == Decimal("86.730000")
    assert usd_to_inr.cached is False
    assert len(fx_calls) == 1

    # 2. Cached lookup reuses cached rate without extra HTTP calls
    cached_conv = await svc.convert_amount(Decimal("10.00"), "USD", "INR")
    assert cached_conv.display_amount == Decimal("867.30")
    assert cached_conv.cached is True
    assert len(fx_calls) == 1

    # 3. INR -> USD conversion
    inr_to_usd = await svc.convert_amount(Decimal("2300.00"), "INR", "USD")
    assert inr_to_usd.original_currency == "INR"
    assert inr_to_usd.display_currency == "USD"
    assert inr_to_usd.display_amount == Decimal("26.52")
    assert len(fx_calls) == 2

    # 4. Same-currency conversion requires no external call
    same = await svc.convert_amount(Decimal("99.95"), "USD", "USD")
    assert same.display_amount == Decimal("99.95")
    assert same.exchange_rate == Decimal("1.000000")
    assert same.source == "identity"
    assert len(fx_calls) == 2


@pytest.mark.asyncio
async def test_exchange_rate_api_failure_never_uses_hardcoded_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx_for_fx_and_external(monkeypatch, fx_status=503)
    svc = ExchangeRateService(get_settings())

    with pytest.raises(ExchangeRateError) as exc_info:
        await svc.convert_amount(Decimal("26.52"), "USD", "INR")
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_product_search_converts_prices_and_filters_inr_budget(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await register_and_login(client, email="fx-search@example.com")
    headers = {"Authorization": f"Bearer {user['tokens']['access_token']}"}

    monkeypatch.setenv("CHANNEL3_API_KEY", "test-channel3-key")
    clear_settings_cache()

    mock_items = [
        {
            "id": "YSD8j4q",
            "title": "KPH7 Headphone",
            "brands": [{"id": "b1", "name": "Koss"}],
            "offers": [
                {
                    "url": "https://buy.example/kph7",
                    "domain": "bestbuy.com",
                    "price": {"price": 26.52, "currency": "USD"},
                    "availability": "InStock",
                }
            ],
        },
        {
            "id": "exp-999",
            "title": "Expensive Studio Headphones",
            "brands": [{"id": "b2", "name": "Sony"}],
            "offers": [
                {
                    "url": "https://buy.example/sony",
                    "domain": "bestbuy.com",
                    "price": {"price": 175.00, "currency": "USD"},
                    "availability": "InStock",
                }
            ],
        },
    ]

    fx_state = _patch_httpx_for_fx_and_external(monkeypatch, channel3_products=mock_items)

    # Budget of 2500 INR should include 26.52 USD (2300.08 INR) and exclude 175 USD (15177.75 INR)
    resp = await client.get(
        "/api/v1/products/search",
        headers=headers,
        params={"query": "headphone", "currency": "INR", "max_price": "2500"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_currency"] == "INR"
    assert Decimal(body["exchange_rate"]) == Decimal("86.730000")
    assert body["total"] == 1
    item = body["products"][0]
    # Original merchant fields remain preserved
    assert Decimal(item["price"]) == Decimal("26.52")
    assert item["currency"] == "USD"
    assert Decimal(item["original_price"]) == Decimal("26.52")
    assert item["original_currency"] == "USD"
    # Display fields hold converted INR amount
    assert Decimal(item["display_price"]) == Decimal("2300.08")
    assert item["display_currency"] == "INR"

    # Single product detail endpoint supports ?currency=INR conversion too
    detail_resp = await client.get(
        f"/api/v1/products/{item['id']}",
        headers=headers,
        params={"currency": "INR"},
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert Decimal(detail["original_price"]) == Decimal("26.52")
    assert detail["original_currency"] == "USD"
    assert Decimal(detail["display_price"]) == Decimal("2300.08")
    assert detail["display_currency"] == "INR"

    # If live FX API fails, search in INR fails transparently (503) instead of faking rates
    from app.services.exchange_rate import clear_exchange_rate_cache

    clear_exchange_rate_cache()
    fx_state["fx_status"] = 503
    fail_resp = await client.get(
        "/api/v1/products/search",
        headers=headers,
        params={"query": "headphone", "currency": "INR"},
    )
    assert fail_resp.status_code == 503


@pytest.mark.asyncio
async def test_cross_currency_product_comparison_in_inr(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await register_and_login(client, email="fx-compare@example.com")
    headers = {"Authorization": f"Bearer {user['tokens']['access_token']}"}

    p_usd = Product(
        external_product_id="cmp-usd-1",
        name="Alpha USB Headphones",
        price=Decimal("100.00"),
        currency="USD",
        merchant="us-merchant.example",
        availability="IN_STOCK",
        provider="channel3",
        is_test_data=False,
    )
    p_eur = Product(
        external_product_id="cmp-eur-1",
        name="Beta Studio Headphones",
        price=Decimal("80.00"),
        currency="EUR",
        merchant="eu-merchant.example",
        availability="IN_STOCK",
        provider="channel3",
        is_test_data=False,
    )
    db_session.add_all([p_usd, p_eur])
    await db_session.commit()

    # 100 USD = 8600 INR (over budget 8000), 80 EUR = 7360 INR (within budget 8000)
    _patch_httpx_for_fx_and_external(
        monkeypatch,
        rates_map={("USD", "INR"): 86.00, ("EUR", "INR"): 92.00},
    )

    resp = await client.post(
        "/api/v1/products/compare",
        headers=headers,
        json={
            "product_ids": [p_usd.id, p_eur.id],
            "budget": "8000",
            "currency": "INR",
            "requirements": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["currency"] == "INR"
    assert Decimal(data["lowest_price"]) == Decimal("7360.00")
    assert Decimal(data["highest_price"]) == Decimal("8600.00")
    assert data["best_value_product_id"] == p_eur.id

    by_id = {item["product_id"]: item for item in data["items"]}
    assert by_id[p_usd.id]["original_currency"] == "USD"
    assert Decimal(by_id[p_usd.id]["original_price"]) == Decimal("100.00")
    assert Decimal(by_id[p_usd.id]["display_price"]) == Decimal("8600.00")
    assert by_id[p_usd.id]["within_budget"] is False

    assert by_id[p_eur.id]["original_currency"] == "EUR"
    assert Decimal(by_id[p_eur.id]["original_price"]) == Decimal("80.00")
    assert Decimal(by_id[p_eur.id]["display_price"]) == Decimal("7360.00")
    assert by_id[p_eur.id]["within_budget"] is True


@pytest.mark.asyncio
async def test_checkout_payment_currency_safety_reconciliation_and_limit_checks(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_info = await register_and_login(client, email="fx-pay@example.com")
    headers = {"Authorization": f"Bearer {user_info['tokens']['access_token']}"}
    user_id = user_info["user"]["id"]

    # Configure user spending limit in INR: max single transaction 3000 INR
    limit_row = (
        await db_session.execute(
            SpendingLimit.__table__.select().where(SpendingLimit.user_id == user_id)
        )
    ).first()
    if limit_row is not None:
        await db_session.execute(
            SpendingLimit.__table__.update()
            .where(SpendingLimit.user_id == user_id)
            .values(
                max_single_transaction=Decimal("3000.00"),
                daily_limit=Decimal("6000.00"),
                monthly_limit=Decimal("20000.00"),
                currency="INR",
            )
        )
    else:
        db_session.add(
            SpendingLimit(
                user_id=user_id,
                max_single_transaction=Decimal("3000.00"),
                daily_limit=Decimal("6000.00"),
                monthly_limit=Decimal("20000.00"),
                currency="INR",
            )
        )

    prod_usd = Product(
        external_product_id="pay-usd-26",
        name="KPH7 Headphone",
        price=Decimal("26.52"),
        currency="USD",
        merchant="bestbuy.com",
        availability="IN_STOCK",
        provider="channel3",
        is_test_data=False,
    )
    prod_over_limit = Product(
        external_product_id="pay-usd-50",
        name="Over Limit DAC",
        price=Decimal("50.00"),
        currency="USD",
        merchant="audio.example",
        availability="IN_STOCK",
        provider="channel3",
        is_test_data=False,
    )
    prod_inr_only = Product(
        external_product_id="pay-inr-only",
        name="Local INR Listing",
        price=Decimal("2000.00"),
        currency="INR",
        merchant="india-store.example",
        availability="IN_STOCK",
        provider="channel3",
        is_test_data=False,
    )
    db_session.add_all([prod_usd, prod_over_limit, prod_inr_only])
    await db_session.commit()

    monkeypatch.setenv("PAYPAL_CLIENT_ID", "sandbox-id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "sandbox-secret")
    clear_settings_cache()

    paypal_bodies: list[dict] = []
    fx_state = _patch_httpx_for_fx_and_external(monkeypatch, paypal_bodies=paypal_bodies)

    # 1. Backend checkout quote for USD item viewed in INR keeps payable currency as USD
    quote_resp = await client.get(
        "/api/v1/payments/quote",
        headers=headers,
        params={"product_id": prod_usd.id, "quantity": 1, "display_currency": "INR"},
    )
    assert quote_resp.status_code == 200
    quote = quote_resp.json()
    assert Decimal(quote["original_amount"]) == Decimal("26.52")
    assert quote["original_currency"] == "USD"
    assert Decimal(quote["display_amount"]) == Decimal("2300.08")
    assert quote["display_currency"] == "INR"
    assert Decimal(quote["payable_amount"]) == Decimal("26.52")
    assert quote["payable_currency"] == "USD"
    assert quote["can_checkout"] is True

    # 2. Frontend submitting INR or converted INR amount as payment expectation is REJECTED (409)
    bad_cur_resp = await client.post(
        "/api/v1/payments/create-order",
        headers=headers,
        json={
            "product_id": prod_usd.id,
            "quantity": 1,
            "expected_amount": "2300.08",
            "expected_currency": "INR",
            "display_currency": "INR",
        },
    )
    assert bad_cur_resp.status_code == 409
    assert len(paypal_bodies) == 0

    bad_amt_resp = await client.post(
        "/api/v1/payments/create-order",
        headers=headers,
        json={
            "product_id": prod_usd.id,
            "quantity": 1,
            "expected_amount": "2300.08",
            "expected_currency": "USD",
            "display_currency": "INR",
        },
    )
    assert bad_amt_resp.status_code == 409
    assert len(paypal_bodies) == 0

    # 3. Legitimate create-order uses backend-verified USD payable amount while storing INR display audit metadata
    ok_resp = await client.post(
        "/api/v1/payments/create-order",
        headers=headers,
        json={
            "product_id": prod_usd.id,
            "quantity": 1,
            "expected_amount": "26.52",
            "expected_currency": "USD",
            "display_currency": "INR",
        },
    )
    assert ok_resp.status_code == 201
    order_data = ok_resp.json()
    assert Decimal(order_data["amount"]) == Decimal("26.52")
    assert order_data["currency"] == "USD"
    assert Decimal(order_data["display_amount"]) == Decimal("2300.08")
    assert order_data["display_currency"] == "INR"
    assert paypal_bodies[0]["purchase_units"][0]["amount"] == {
        "currency_code": "USD",
        "value": "26.52",
    }

    # 4. Cross-currency spending limit blocks 50 USD (~4336.50 INR) against 3000 INR limit
    limit_resp = await client.post(
        "/api/v1/payments/create-order",
        headers=headers,
        json={"product_id": prod_over_limit.id, "quantity": 1},
    )
    assert limit_resp.status_code == 403

    # Also verify SecurityAgent blocks cross-currency limit violation deterministically
    user_obj = await db_session.get(User, user_id)
    assert user_obj is not None
    sec_agent = SecurityAgent(settings=get_settings())
    sec_res = await sec_agent.execute(
        "Check cross-currency limit",
        session=db_session,
        user=user_obj,
        product=prod_over_limit,
        quantity=1,
    )
    assert sec_res.data is not None
    assert sec_res.data.block_execution is True

    # 5. Product in unsupported PayPal currency (INR) is BLOCKED safely if FX conversion fails
    from app.services.exchange_rate import clear_exchange_rate_cache

    clear_exchange_rate_cache()
    fx_state["fx_status"] = 503
    blocked_quote = await client.get(
        "/api/v1/payments/quote",
        headers=headers,
        params={"product_id": prod_inr_only.id, "quantity": 1},
    )
    assert blocked_quote.status_code == 200
    assert blocked_quote.json()["can_checkout"] is False
    assert blocked_quote.json()["blocking_reason"]

    blocked_order = await client.post(
        "/api/v1/payments/create-order",
        headers=headers,
        json={"product_id": prod_inr_only.id, "quantity": 1},
    )
    assert blocked_order.status_code == 422
    assert len(paypal_bodies) == 1
