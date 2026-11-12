from __future__ import annotations

import json
import os
from decimal import Decimal

import httpx
import pytest

from app.core.config import clear_settings_cache
from app.integrations.paypal.client import PayPalClient
from tests.conftest import register_and_login


async def _seed_test_product(client: httpx.AsyncClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setenv("ENABLE_TEST_PRODUCT_FIXTURES", "true")
    clear_settings_cache()
    resp = await client.get(
        "/api/v1/products/search",
        headers=headers,
        params={"query": "headphones"},
    )
    assert resp.status_code == 200
    products = resp.json()["products"]
    assert len(products) >= 1
    return products[0]


@pytest.mark.asyncio
async def test_paypal_order_creation_validation_capture_and_security(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buyer1 = await register_and_login(client, email="buyer1@example.com")
    buyer2 = await register_and_login(client, email="buyer2@example.com")
    h1 = {"Authorization": f"Bearer {buyer1['tokens']['access_token']}"}
    h2 = {"Authorization": f"Bearer {buyer2['tokens']['access_token']}"}

    product = await _seed_test_product(client, h1, monkeypatch)
    unit_price = Decimal(product["price"])  # 279.99

    monkeypatch.setenv("PAYPAL_CLIENT_ID", "sandbox-client-id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "sandbox-client-secret")
    clear_settings_cache()

    paypal_state = {"order_status": "CREATED", "captured": False, "oauth_calls": 0}

    def paypal_mock(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/v1/oauth2/token"):
            paypal_state["oauth_calls"] += 1
            return httpx.Response(200, json={"access_token": "tok_cached", "expires_in": 3600})
        if url.endswith("/v2/checkout/orders") and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            # Verify backend sent exact unit_price
            assert body["purchase_units"][0]["amount"]["value"] == str(unit_price)
            return httpx.Response(
                201,
                json={
                    "id": "PP-ORD-100",
                    "status": "PAYER_ACTION_REQUIRED",
                    "links": [{"rel": "payer-action", "href": "https://sandbox.paypal.com/approve/100"}],
                },
            )
        if url.endswith("/v2/checkout/orders/PP-ORD-100") and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": "PP-ORD-100",
                    "status": paypal_state["order_status"],
                    "purchase_units": [
                        {
                            "amount": {"currency_code": "USD", "value": str(unit_price)},
                            **(
                                {
                                    "payments": {
                                        "captures": [
                                            {"id": "PP-CAP-100", "status": "COMPLETED"}
                                        ]
                                    }
                                }
                                if paypal_state["captured"]
                                else {}
                            ),
                        }
                    ],
                },
            )
        if url.endswith("/v2/checkout/orders/PP-ORD-100/capture") and request.method == "POST":
            paypal_state["order_status"] = "COMPLETED"
            paypal_state["captured"] = True
            return httpx.Response(
                201,
                json={
                    "id": "PP-ORD-100",
                    "status": "COMPLETED",
                    "purchase_units": [
                        {
                            "payments": {
                                "captures": [
                                    {
                                        "id": "PP-CAP-100",
                                        "status": "COMPLETED",
                                        "amount": {"currency_code": "USD", "value": str(unit_price)},
                                    }
                                ]
                            }
                        }
                    ],
                },
            )
        return httpx.Response(404)

    orig_async_client = httpx.AsyncClient
    mock_transport = httpx.MockTransport(paypal_mock)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: orig_async_client(*a, **{**kw, "transport": mock_transport}),
    )

    # 1. Tampered frontend amount rejected (409)
    tamper_resp = await client.post(
        "/api/v1/payments/create-order",
        headers=h1,
        json={"product_id": product["id"], "quantity": 1, "expected_amount": "1.00"},
    )
    assert tamper_resp.status_code == 409

    # 2. Exceeding single-transaction spending limit rejected (default limit 500.00; 2 * 279.99 = 559.98)
    limit_resp = await client.post(
        "/api/v1/payments/create-order",
        headers=h1,
        json={"product_id": product["id"], "quantity": 2},
    )
    assert limit_resp.status_code == 403

    # 3. Invalid product rejected
    missing_prod = await client.post(
        "/api/v1/payments/create-order",
        headers=h1,
        json={"product_id": "nonexistent-product", "quantity": 1},
    )
    assert missing_prod.status_code == 404

    # 4. Valid order creation with idempotency
    create_resp = await client.post(
        "/api/v1/payments/create-order",
        headers=h1,
        json={
            "product_id": product["id"],
            "quantity": 1,
            "idempotency_key": "pay-idem-1000",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    order = create_resp.json()
    assert order["paypal_order_id"] == "PP-ORD-100"
    assert order["status"] == "PENDING_APPROVAL"
    assert Decimal(order["amount"]) == unit_price

    # Repeat with same idempotency_key returns same order
    repeat_create = await client.post(
        "/api/v1/payments/create-order",
        headers=h1,
        json={
            "product_id": product["id"],
            "quantity": 1,
            "idempotency_key": "pay-idem-1000",
        },
    )
    assert repeat_create.status_code == 201
    assert repeat_create.json()["id"] == order["id"]

    # 5. Cross-user access / unauthorized capture rejected (403)
    other_get = await client.get(f"/api/v1/payments/{order['id']}", headers=h2)
    assert other_get.status_code == 403
    other_cap = await client.post(
        f"/api/v1/payments/{order['id']}/capture", headers=h2
    )
    assert other_cap.status_code == 403

    # 6. Capture rejected before PayPal confirms APPROVED
    premature_cap = await client.post(
        f"/api/v1/payments/{order['id']}/capture", headers=h1
    )
    assert premature_cap.status_code == 409

    # 7. Simulate buyer approving order on PayPal -> status verification + capture succeed
    paypal_state["order_status"] = "APPROVED"
    status_resp = await client.get(f"/api/v1/payments/{order['id']}", headers=h1)
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "APPROVED"

    cap_resp = await client.post(
        f"/api/v1/payments/{order['id']}/capture", headers=h1
    )
    assert cap_resp.status_code == 200, cap_resp.text
    assert cap_resp.json()["status"] == "COMPLETED"

    # Verify OAuth2 token was cached across multiple PayPal API calls
    assert paypal_state["oauth_calls"] == 1

    # 8. Duplicate capture prevention
    dup_cap = await client.post(
        f"/api/v1/payments/{order['id']}/capture", headers=h1
    )
    assert dup_cap.status_code == 409

    # 9. Transaction & summary reflect exact Decimal spend
    tx_list = await client.get("/api/v1/transactions", headers=h1)
    assert tx_list.status_code == 200
    assert tx_list.json()["total"] == 1
    assert tx_list.json()["transactions"][0]["paypal_capture_id"] == "PP-CAP-100"

    tx_summary = await client.get("/api/v1/transactions/summary", headers=h1)
    assert tx_summary.status_code == 200
    assert tx_summary.json()["completed_count"] == 1
    assert Decimal(tx_summary.json()["total_spent_by_currency"]["USD"]) == unit_price


@pytest.mark.asyncio
async def test_cancel_uncaptured_payment_order(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buyer = await register_and_login(client, email="canceller@example.com")
    headers = {"Authorization": f"Bearer {buyer['tokens']['access_token']}"}
    product = await _seed_test_product(client, headers, monkeypatch)

    monkeypatch.setenv("PAYPAL_CLIENT_ID", "sandbox-client-id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "sandbox-client-secret")
    clear_settings_cache()

    def paypal_mock(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/v1/oauth2/token"):
            return httpx.Response(200, json={"access_token": "tok_cancel", "expires_in": 3600})
        if str(request.url).endswith("/v2/checkout/orders") and request.method == "POST":
            return httpx.Response(201, json={"id": "PP-ORD-CANCEL", "status": "CREATED", "links": []})
        return httpx.Response(404)

    orig_async_client = httpx.AsyncClient
    mock_transport = httpx.MockTransport(paypal_mock)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: orig_async_client(*a, **{**kw, "transport": mock_transport}),
    )

    create_resp = await client.post(
        "/api/v1/payments/create-order",
        headers=headers,
        json={"product_id": product["id"], "quantity": 1},
    )
    assert create_resp.status_code == 201
    order_id = create_resp.json()["id"]

    cancel_resp = await client.post(
        f"/api/v1/payments/{order_id}/cancel",
        headers=headers,
        json={"reason": "Changed mind"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_paypal_order_preserves_usd_with_inr_display_and_records_merchant_diagnostics(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buyer = await register_and_login(client, email="indiadiag@example.com")
    headers = {"Authorization": f"Bearer {buyer['tokens']['access_token']}"}
    product = await _seed_test_product(client, headers, monkeypatch)
    unit_price = Decimal(product["price"])  # 279.99 USD

    monkeypatch.setenv("PAYPAL_CLIENT_ID", "sandbox-client-id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "sandbox-client-secret")
    monkeypatch.setenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
    clear_settings_cache()

    captured_paypal_bodies: list[dict] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "api.frankfurter.dev" in url:
            return httpx.Response(
                200,
                json={"amount": 1.0, "base": "USD", "date": "2026-11-12", "rates": {"INR": 94.0}},
            )
        if url.endswith("/v1/oauth2/token"):
            return httpx.Response(200, json={"access_token": "tok_diag", "expires_in": 3600})
        if url.endswith("/v2/checkout/orders") and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            captured_paypal_bodies.append(body)
            return httpx.Response(
                201,
                json={
                    "id": "PP-ORD-DIAG",
                    "status": "PAYER_ACTION_REQUIRED",
                    "links": [{"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=PP-ORD-DIAG"}],
                },
            )
        if url.endswith("/v2/checkout/orders/PP-ORD-DIAG") and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": "PP-ORD-DIAG",
                    "intent": "CAPTURE",
                    "status": "PAYER_ACTION_REQUIRED",
                    "payment_source": {"paypal": {}},
                    "purchase_units": [
                        {
                            "amount": {"currency_code": "USD", "value": str(unit_price)},
                            "payee": {
                                "merchant_id": "8KF3K9RFMJEGG",
                                "email_address": "sb-merchant@business.example.com",
                            },
                        }
                    ],
                    "payer": {"address": {"country_code": "IN"}},
                },
            )
        if url.endswith("/v1/customer/partners/8KF3K9RFMJEGG/merchant-integrations/8KF3K9RFMJEGG"):
            return httpx.Response(
                200,
                json={
                    "merchant_id": "8KF3K9RFMJEGG",
                    "country": "IN",
                    "payments_receivable": True,
                },
            )
        return httpx.Response(404)

    orig_async_client = httpx.AsyncClient
    mock_transport = httpx.MockTransport(mock_handler)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: orig_async_client(*a, **{**kw, "transport": mock_transport}),
    )

    quote_resp = await client.get(
        "/api/v1/payments/quote",
        headers=headers,
        params={"product_id": product["id"], "quantity": 1, "display_currency": "INR"},
    )
    assert quote_resp.status_code == 200, quote_resp.text
    quote = quote_resp.json()
    assert quote["original_currency"] == "USD"
    assert quote["display_currency"] == "INR"
    assert quote["payable_currency"] == "USD"
    assert Decimal(quote["payable_amount"]) == unit_price

    create_resp = await client.post(
        "/api/v1/payments/create-order",
        headers=headers,
        json={
            "product_id": product["id"],
            "quantity": 1,
            "display_currency": "INR",
            "expected_currency": "USD",
            "expected_amount": str(unit_price),
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    assert created["currency"] == "USD"
    assert captured_paypal_bodies[0]["purchase_units"][0]["amount"] == {
        "currency_code": "USD",
        "value": str(unit_price),
    }

    sync_resp = await client.get(f"/api/v1/payments/{created['id']}?sync=true", headers=headers)
    assert sync_resp.status_code == 200, sync_resp.text
    synced = sync_resp.json()
    assert synced["order_snapshot"]["paypal_payee_merchant_id"] == "8KF3K9RFMJEGG"
    assert synced["order_snapshot"]["paypal_merchant_country"] == "IN"
    assert synced["order_snapshot"]["paypal_payer_country"] == "IN"


@pytest.mark.skipif(
    os.getenv("RUN_PAYPAL_SANDBOX_TESTS") != "1"
    or not os.getenv("PAYPAL_CLIENT_ID")
    or not os.getenv("PAYPAL_CLIENT_SECRET"),
    reason="Manual PayPal Sandbox integration test (set RUN_PAYPAL_SANDBOX_TESTS=1 and sandbox credentials).",
)
@pytest.mark.asyncio
async def test_manual_paypal_sandbox_oauth_connectivity() -> None:
    """Manual verification test against real PayPal Sandbox OAuth2 API."""
    clear_settings_cache()
    pp_client = PayPalClient()
    health = await pp_client.check_health(verify_remote=True)
    assert health["status"] == "HEALTHY"
    assert health["environment"] == "sandbox"

