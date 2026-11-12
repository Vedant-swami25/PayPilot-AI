from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.models.order import Order
from app.models.transaction import Transaction
from tests.conftest import register_and_login

_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _webhook_headers() -> dict[str, str]:
    return {
        "PAYPAL-TRANSMISSION-ID": "trans-id-123",
        "PAYPAL-TRANSMISSION-TIME": "2026-11-12T10:00:00Z",
        "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-1",
        "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        "PAYPAL-TRANSMISSION-SIG": "valid-signature-mock",
    }


async def _create_pending_order(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, str], dict]:
    buyer = await register_and_login(client, email="webhookbuyer@example.com")
    headers = {"Authorization": f"Bearer {buyer['tokens']['access_token']}"}

    monkeypatch.setenv("ENABLE_TEST_PRODUCT_FIXTURES", "true")
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "pp-id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "pp-secret")
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-123456")
    clear_settings_cache()

    search_resp = await client.get(
        "/api/v1/products/search", headers=headers, params={"query": "headphones"}
    )
    product = search_resp.json()["products"][0]

    def mock_paypal(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/v1/oauth2/token"):
            return httpx.Response(200, json={"access_token": "tok_wh", "expires_in": 3600})
        if url.endswith("/v2/checkout/orders") and request.method == "POST":
            return httpx.Response(
                201,
                json={"id": "PP-ORD-WH-1", "status": "PAYER_ACTION_REQUIRED", "links": []},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_paypal)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: _REAL_ASYNC_CLIENT(*a, **{**kw, "transport": transport}),
    )

    order_resp = await client.post(
        "/api/v1/payments/create-order",
        headers=headers,
        json={"product_id": product["id"], "quantity": 1},
    )
    assert order_resp.status_code == 201
    return headers, order_resp.json()


@pytest.mark.asyncio
async def test_webhook_signature_verification_and_duplicate_idempotency(
    client: httpx.AsyncClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, order = await _create_pending_order(client, monkeypatch)

    verify_status = {"status": "FAILURE"}

    def webhook_paypal_mock(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/v1/oauth2/token"):
            return httpx.Response(200, json={"access_token": "tok_wh", "expires_in": 3600})
        if url.endswith("/v1/notifications/verify-webhook-signature"):
            return httpx.Response(200, json={"verification_status": verify_status["status"]})
        return httpx.Response(404)

    transport = httpx.MockTransport(webhook_paypal_mock)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: _REAL_ASYNC_CLIENT(*a, **{**kw, "transport": transport}),
    )

    approved_event = {
        "id": "WH-EVT-001",
        "event_type": "CHECKOUT.ORDER.APPROVED",
        "resource": {"id": "PP-ORD-WH-1"},
    }

    # 1. Missing headers rejected
    no_headers = await client.post("/api/v1/webhooks/paypal", json=approved_event)
    assert no_headers.status_code == 400

    # 2. Failed signature verification rejected (401) without modifying order
    bad_sig = await client.post(
        "/api/v1/webhooks/paypal", headers=_webhook_headers(), json=approved_event
    )
    assert bad_sig.status_code == 401

    # 3. Valid signature updates order to APPROVED
    verify_status["status"] = "SUCCESS"
    ok_sig = await client.post(
        "/api/v1/webhooks/paypal", headers=_webhook_headers(), json=approved_event
    )
    assert ok_sig.status_code == 200
    assert ok_sig.json()["duplicate"] is False
    assert ok_sig.json()["status"] == "PROCESSED"

    # 4. Duplicate event ID handled idempotently
    dup_sig = await client.post(
        "/api/v1/webhooks/paypal", headers=_webhook_headers(), json=approved_event
    )
    assert dup_sig.status_code == 200
    assert dup_sig.json()["duplicate"] is True

    # 5. Verified PAYMENT.CAPTURE.COMPLETED transitions Order & Transaction to COMPLETED
    captured_event = {
        "id": "WH-EVT-002",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "PP-CAP-WH-1",
            "amount": {"currency_code": order["currency"], "value": str(order["amount"])},
            "supplementary_data": {"related_ids": {"order_id": "PP-ORD-WH-1"}},
        },
    }
    cap_wh = await client.post(
        "/api/v1/webhooks/paypal", headers=_webhook_headers(), json=captured_event
    )
    assert cap_wh.status_code == 200
    assert cap_wh.json()["status"] == "PROCESSED"

    # Out-of-order late CHECKOUT.ORDER.APPROVED must NOT downgrade COMPLETED
    late_approved = {
        "id": "WH-EVT-003",
        "event_type": "CHECKOUT.ORDER.APPROVED",
        "resource": {"id": "PP-ORD-WH-1"},
    }
    late_resp = await client.post(
        "/api/v1/webhooks/paypal", headers=_webhook_headers(), json=late_approved
    )
    assert late_resp.status_code == 200
    assert late_resp.json()["status"] == "IGNORED_OUT_OF_ORDER"

    res = await db_session.execute(select(Order).where(Order.id == order["id"]))
    persisted_order = res.scalar_one()
    assert persisted_order.status == "COMPLETED"

    tx_res = await db_session.execute(
        select(Transaction).where(Transaction.order_id == order["id"])
    )
    tx = tx_res.scalar_one()
    assert tx.status == "COMPLETED"
    assert tx.paypal_capture_id == "PP-CAP-WH-1"

    # 6. Refund webhook transitions to REFUNDED
    refund_event = {
        "id": "WH-EVT-004",
        "event_type": "PAYMENT.CAPTURE.REFUNDED",
        "resource": {
            "id": "PP-REF-WH-1",
            "supplementary_data": {
                "related_ids": {"order_id": "PP-ORD-WH-1", "capture_id": "PP-CAP-WH-1"}
            },
        },
    }
    ref_resp = await client.post(
        "/api/v1/webhooks/paypal", headers=_webhook_headers(), json=refund_event
    )
    assert ref_resp.status_code == 200
    assert ref_resp.json()["status"] == "PROCESSED"

    await db_session.refresh(persisted_order)
    assert persisted_order.status == "REFUNDED"


@pytest.mark.asyncio
async def test_webhook_capture_denied_marks_order_failed(
    client: httpx.AsyncClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, order = await _create_pending_order(client, monkeypatch)

    def denied_mock(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/v1/oauth2/token"):
            return httpx.Response(200, json={"access_token": "tok_wh2", "expires_in": 3600})
        if url.endswith("/v1/notifications/verify-webhook-signature"):
            return httpx.Response(200, json={"verification_status": "SUCCESS"})
        return httpx.Response(404)

    transport = httpx.MockTransport(denied_mock)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: _REAL_ASYNC_CLIENT(*a, **{**kw, "transport": transport}),
    )

    denied_event = {
        "id": "WH-EVT-DENIED-1",
        "event_type": "PAYMENT.CAPTURE.DENIED",
        "resource": {
            "id": "PP-CAP-DENIED-1",
            "supplementary_data": {"related_ids": {"order_id": "PP-ORD-WH-1"}},
        },
    }
    resp = await client.post(
        "/api/v1/webhooks/paypal", headers=_webhook_headers(), json=denied_event
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PROCESSED"

    res = await db_session.execute(select(Order).where(Order.id == order["id"]))
    persisted_order = res.scalar_one()
    assert persisted_order.status == "FAILED"
