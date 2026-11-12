from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

from app.core.config import Settings, clear_settings_cache, get_settings
from app.core.security import create_access_token
from app.llm import LLMResponse
from app.llm.router import LLMRouter
from tests.conftest import register_and_login


@pytest.mark.asyncio
async def test_health_endpoints_safe_when_unconfigured(
    client: httpx.AsyncClient,
) -> None:
    root = await client.get("/health")
    assert root.status_code == 200
    assert root.json()["status"] == "HEALTHY"

    v1 = await client.get("/api/v1/health")
    assert v1.status_code == 200
    body = v1.json()
    assert body["integrations"]["database"]["status"] == "HEALTHY"
    assert body["integrations"]["ai"]["status"] == "NOT_CONFIGURED"
    assert body["integrations"]["paypal"]["status"] == "NOT_CONFIGURED"

    ai_h = await client.get("/api/v1/health/ai")
    assert ai_h.status_code == 200
    assert ai_h.json()["status"] == "NOT_CONFIGURED"

    pp_h = await client.get("/api/v1/health/paypal")
    assert pp_h.status_code == 200
    assert pp_h.json()["status"] == "NOT_CONFIGURED"

    # Confirm Swagger & ReDoc are accessible
    docs = await client.get("/docs")
    assert docs.status_code == 200
    redoc = await client.get("/redoc")
    assert redoc.status_code == 200


@pytest.mark.asyncio
async def test_authentication_lifecycle_and_security(
    client: httpx.AsyncClient,
) -> None:
    # 1. Unauthorized access rejected
    me_unauth = await client.get("/api/v1/auth/me")
    assert me_unauth.status_code == 401

    # 2. Register
    auth = await register_and_login(
        client, name="Jane Pilot", email="jane@example.com", password="Password123!"
    )
    access_token = auth["tokens"]["access_token"]
    refresh_token = auth["tokens"]["refresh_token"]
    user_id = auth["user"]["id"]

    # Duplicate email returns 409
    dup = await client.post(
        "/api/v1/auth/register",
        json={"name": "Jane 2", "email": "jane@example.com", "password": "Password123!"},
    )
    assert dup.status_code == 409

    # 3. Invalid credentials
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "jane@example.com", "password": "WrongPassword1!"},
    )
    assert bad_login.status_code == 401

    # 4. Valid login & profile retrieval/update
    ok_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "jane@example.com", "password": "Password123!"},
    )
    assert ok_login.status_code == 200

    headers = {"Authorization": f"Bearer {access_token}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "jane@example.com"

    upd = await client.put(
        "/api/v1/auth/me",
        headers=headers,
        json={"name": "Jane Updated", "max_single_transaction": "400.00"},
    )
    assert upd.status_code == 200
    assert upd.json()["name"] == "Jane Updated"
    assert Decimal(upd.json()["spending_limit"]["max_single_transaction"]) == Decimal("400.00")

    # 5. Expired access token rejected
    expired_token, _, _ = create_access_token(
        user_id=user_id,
        email="jane@example.com",
        settings=get_settings(),
        expires_delta=timedelta(seconds=-10),
    )
    exp_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert exp_resp.status_code == 401

    # 6. Refresh token rotation & reuse attack detection
    ref_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert ref_resp.status_code == 200
    rotated_refresh = ref_resp.json()["refresh_token"]
    assert rotated_refresh != refresh_token

    # Reusing already-rotated refresh token revokes the entire token family
    reuse_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert reuse_resp.status_code == 401

    # Even the newly rotated token in the same family is now revoked
    after_reuse = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": rotated_refresh},
    )
    assert after_reuse.status_code == 401

    # 7. Logout
    logout_resp = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200


@pytest.mark.asyncio
async def test_login_rate_limiting(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_AUTH_REQUESTS", "3")
    monkeypatch.setenv("RATE_LIMIT_AUTH_WINDOW_SECONDS", "60")
    clear_settings_cache()

    for _ in range(3):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "BadPassword123!"},
        )
        assert resp.status_code == 401

    limited = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "BadPassword123!"},
    )
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


@pytest.mark.asyncio
async def test_product_discovery_comparison_and_workflow_approval(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Initially Channel3 is NOT_CONFIGURED and fixtures disabled -> returns NOT_CONFIGURED cleanly
    auth = await register_and_login(client, email="shopper@example.com")
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    unconf_search = await client.get(
        "/api/v1/products/search", headers=headers, params={"query": "headphones"}
    )
    assert unconf_search.status_code == 200
    assert unconf_search.json()["provider_status"] == "NOT_CONFIGURED"
    assert unconf_search.json()["products"] == []

    # Enable explicit TEST DATA fixtures + mock Nemotron + mock PayPal for workflow approval
    monkeypatch.setenv("ENABLE_TEST_PRODUCT_FIXTURES", "true")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")
    monkeypatch.setenv("NVIDIA_MODEL", "nvidia/nemotron-test")
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "pp-client-id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "pp-client-secret")
    clear_settings_cache()

    search_resp = await client.get(
        "/api/v1/products/search",
        headers=headers,
        params={"query": "headphones", "max_price": "300"},
    )
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["is_test_data"] is True
    assert search_data["total"] == 2
    product_ids = [p["id"] for p in search_data["products"]]

    # Deterministic comparison endpoint
    cmp_resp = await client.post(
        "/api/v1/products/compare",
        headers=headers,
        json={
            "product_ids": product_ids,
            "budget": "260.00",
            "currency": "USD",
            "requirements": ["anc", "usb_c_charging"],
        },
    )
    assert cmp_resp.status_code == 200
    cmp_data = cmp_resp.json()
    assert Decimal(cmp_data["lowest_price"]) == Decimal("249.00")
    assert Decimal(cmp_data["highest_price"]) == Decimal("279.99")
    assert Decimal(cmp_data["price_spread"]) == Decimal("30.99")

    # Mock Nemotron + PayPal HTTP calls for end-to-end commerce workflow + approval
    async def fake_primary(self, *, system_prompt: str, user_prompt: str, schema, **kwargs):
        name = schema.__name__
        if name == "LeadPlanOutput":
            obj = schema.model_validate(
                {
                    "search_query": "headphones",
                    "category": "headphones",
                    "budget": 300,
                    "currency": "USD",
                    "specifications": ["anc"],
                    "execution_plan": [],
                    "reasoning_summary": "ANC headphones under $300",
                }
            )
        elif name == "_LLMDecisionPayload":
            payload = json.loads(user_prompt)
            obj = schema.model_validate(
                {
                    "recommended_product_id": payload["deterministic_top_product_id"],
                    "recommendation_rationale": "Best value under $300 with ANC.",
                    "trade_offs": ["Battery vs price"],
                }
            )
        else:
            payload = json.loads(user_prompt)
            obj = schema.model_validate(
                {
                    "executive_summary": "Approved recommendation ready.",
                    "recommended_product_id": payload["recommendation"]["recommended_product_id"],
                    "ready_for_user_approval": True,
                    "blocking_reasons": [],
                }
            )
        return obj, LLMResponse(
            provider="nvidia_nemotron", model="nvidia/nemotron-test", content="{}", latency_ms=5.0
        )

    monkeypatch.setattr(LLMRouter, "generate_primary_structured", fake_primary)

    def paypal_handler(request: httpx.Request) -> httpx.Response:
        if "/v1/oauth2/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "pp_tok_123", "expires_in": 3600})
        if str(request.url).endswith("/v2/checkout/orders") and request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "id": "PAYPAL-ORDER-999",
                    "status": "PAYER_ACTION_REQUIRED",
                    "links": [
                        {
                            "rel": "payer-action",
                            "href": "https://www.sandbox.paypal.com/checkoutnow?token=PAYPAL-ORDER-999",
                            "method": "GET",
                        }
                    ],
                },
            )
        return httpx.Response(404)

    orig_async_client = httpx.AsyncClient
    mock_transport = httpx.MockTransport(paypal_handler)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: orig_async_client(*a, **{**kw, "transport": mock_transport}),
    )

    wf_resp = await client.post(
        "/api/v1/commerce/request",
        headers=headers,
        json={"request_text": "Buy ANC headphones under $300", "budget": "300.00"},
    )
    assert wf_resp.status_code == 200
    wf = wf_resp.json()
    assert wf["status"] == "AWAITING_USER_APPROVAL"

    # Explicit user approval creates PayPal order cleanly
    approve_resp = await client.post(
        f"/api/v1/commerce/workflows/{wf['id']}/approve",
        headers=headers,
        json={"confirm_purchase": True, "quantity": 1, "create_paypal_order": True},
    )
    assert approve_resp.status_code == 200, approve_resp.text
    approved_body = approve_resp.json()
    assert approved_body["workflow"]["status"] == "ORDER_CREATED"
    assert approved_body["payment_order"]["paypal_order_id"] == "PAYPAL-ORDER-999"
    assert approved_body["payment_order"]["status"] == "PENDING_APPROVAL"

    # Resumable re-call to /approve returns the existing order instead of creating duplicates
    resume_resp = await client.post(
        f"/api/v1/commerce/workflows/{wf['id']}/approve",
        headers=headers,
        json={"confirm_purchase": True, "quantity": 1, "create_paypal_order": True},
    )
    assert resume_resp.status_code == 200
    assert resume_resp.json()["payment_order"]["id"] == approved_body["payment_order"]["id"]

    # History check
    hist_resp = await client.get("/api/v1/commerce/history", headers=headers)
    assert hist_resp.status_code == 200
    assert hist_resp.json()["total"] == 1


def test_settings_loads_comma_separated_cors_origins_from_dotenv(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APP_ENV=development\nCORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=env_file)
    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]

    json_env_file = tmp_path / ".env.json"
    json_env_file.write_text(
        'APP_ENV=development\nCORS_ORIGINS=["http://localhost:5173"]\n',
        encoding="utf-8",
    )
    json_settings = Settings(_env_file=json_env_file)
    assert json_settings.cors_origins == ["http://localhost:5173"]
