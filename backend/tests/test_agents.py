from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.agents import AgentExecutionStatus
from app.agents.lead_agent import LeadAgent, LeadPlanOutput
from app.agents.orchestrator import CommerceOrchestrator
from app.core.config import clear_settings_cache, get_settings
from app.integrations.products.provider import TestFixtureProductProvider
from app.llm import LLMResponse, LLMResponseParseError
from app.llm.router import LLMRouter
from app.services.product_service import ProductService
from tests.conftest import register_and_login


class _FakeTransportHandler:
    """Deterministic mock responder for OpenAI-compatible LLM endpoints."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8")) if request.content else {}
        url = str(request.url)
        self.calls.append({"url": url, "model": body.get("model"), "body": body})

        for key, outcome in self.responses.items():
            if key in url:
                if callable(outcome):
                    return outcome(request, body)
                return outcome
        return httpx.Response(500, json={"error": "unmocked url"})


def _openai_json_response(content_obj: dict[str, Any], model: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "model": model,
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": json.dumps(content_obj)}}
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 40, "total_tokens": 90},
        },
    )


@pytest.mark.asyncio
async def test_lead_agent_requires_nemotron_without_silent_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Configure Mistral and Groq, leave NVIDIA Nemotron unconfigured
    monkeypatch.setenv("MISTRAL_API_KEY", "mistral-key")
    monkeypatch.setenv("MISTRAL_MODEL", "mistral-large-latest")
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    clear_settings_cache()

    lead = LeadAgent(settings=get_settings())
    result = await lead.execute(
        "Parse shopping intent",
        mode="plan",
        request_text="Buy wireless ANC headphones under $300",
    )

    assert result.status == AgentExecutionStatus.NOT_CONFIGURED
    assert "Nemotron" in (result.error or "")


@pytest.mark.asyncio
async def test_lead_agent_execution_and_provider_failure_no_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")
    monkeypatch.setenv("NVIDIA_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct")
    monkeypatch.setenv("MISTRAL_API_KEY", "mistral-test-key")
    monkeypatch.setenv("MISTRAL_MODEL", "mistral-large-latest")
    clear_settings_cache()

    # 1. Valid structured Nemotron response
    plan_json = {
        "search_query": "noise cancelling wireless headphones",
        "category": "headphones",
        "budget": 300,
        "currency": "USD",
        "specifications": ["anc", "bluetooth"],
        "brand_preferences": [],
        "missing_information": [],
        "needs_clarification": False,
        "execution_plan": [
            {"step": "DISCOVERY_AGENT", "goal": "Search catalog"},
        ],
        "reasoning_summary": "Parsed ANC wireless headphones under 300 USD.",
    }
    mock_transport = httpx.MockTransport(
        _FakeTransportHandler(
            {"integrate.api.nvidia.com": _openai_json_response(plan_json, "nemotron-test")}
        ).handler
    )

    orig_async_client = httpx.AsyncClient

    def patched_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = mock_transport
        return orig_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched_client)

    lead = LeadAgent(settings=get_settings())
    ok_res = await lead.execute(
        "Plan shopping",
        mode="plan",
        request_text="Find wireless noise cancelling headphones under $300",
    )
    assert ok_res.status == AgentExecutionStatus.SUCCESS
    assert ok_res.data is not None
    assert ok_res.data.search_query == "noise cancelling wireless headphones"
    assert ok_res.data.budget == Decimal("300.00")

    # 2. Provider failure on Nemotron MUST fail explicitly instead of silently switching to Mistral
    fail_transport = httpx.MockTransport(
        _FakeTransportHandler(
            {
                "integrate.api.nvidia.com": httpx.Response(503, json={"error": "down"}),
                "api.mistral.ai": _openai_json_response(plan_json, "mistral-test"),
            }
        ).handler
    )
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: orig_async_client(*a, **{**kw, "transport": fail_transport}),
    )

    fail_res = await lead.execute(
        "Plan shopping",
        mode="plan",
        request_text="Find wireless headphones",
    )
    assert fail_res.status == AgentExecutionStatus.FAILED
    assert "Nemotron" in (fail_res.error or "")


@pytest.mark.asyncio
async def test_llm_invalid_structured_response_raises_parse_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")
    monkeypatch.setenv("NVIDIA_MODEL", "nvidia/nemotron-test")
    clear_settings_cache()

    bad_transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200,
            json={
                "model": "nemotron-test",
                "choices": [{"message": {"content": "Not valid JSON at all!"}}],
            },
        )
    )
    orig_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: orig_async_client(*a, **{**kw, "transport": bad_transport}),
    )

    router = LLMRouter(get_settings())
    with pytest.raises(LLMResponseParseError):
        await router.nemotron.generate_structured(
            system_prompt="Return JSON",
            user_prompt="Hello",
            schema=LeadPlanOutput,
        )


@pytest.mark.asyncio
async def test_multi_agent_orchestration_delegation_and_cancellation(
    client: httpx.AsyncClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")
    monkeypatch.setenv("NVIDIA_MODEL", "nvidia/nemotron-test")
    monkeypatch.setenv("ENABLE_TEST_PRODUCT_FIXTURES", "true")
    clear_settings_cache()

    auth_data = await register_and_login(client, email="agentflow@example.com")
    headers = {"Authorization": f"Bearer {auth_data['tokens']['access_token']}"}

    # Mock Nemotron responses for Plan -> Decision -> Synthesis
    async def fake_generate_primary(self, *, system_prompt: str, user_prompt: str, schema, **kwargs):
        name = schema.__name__
        if name == "LeadPlanOutput":
            obj = schema.model_validate(
                {
                    "search_query": "headphones",
                    "category": "headphones",
                    "budget": 300,
                    "currency": "USD",
                    "specifications": ["anc"],
                    "brand_preferences": [],
                    "missing_information": [],
                    "needs_clarification": False,
                    "execution_plan": [
                        {"step": "DISCOVERY_AGENT", "goal": "Search products"},
                        {"step": "COMPARISON_AGENT", "goal": "Compare products"},
                    ],
                    "reasoning_summary": "Under $300 ANC headphones.",
                }
            )
        elif name == "_LLMDecisionPayload":
            payload = json.loads(user_prompt)
            top_id = payload["deterministic_top_product_id"]
            obj = schema.model_validate(
                {
                    "recommended_product_id": top_id,
                    "recommendation_rationale": "Matches ANC requirement and stays under $300.",
                    "trade_offs": ["Higher battery life vs slightly lower price."],
                }
            )
        else:
            payload = json.loads(user_prompt)
            rec_id = (payload.get("recommendation") or {}).get("recommended_product_id")
            obj = schema.model_validate(
                {
                    "executive_summary": "Ready for explicit user approval.",
                    "recommended_product_id": rec_id,
                    "ready_for_user_approval": True,
                    "blocking_reasons": [],
                }
            )
        return obj, LLMResponse(
            provider="nvidia_nemotron",
            model="nvidia/nemotron-test",
            content="{}",
            latency_ms=12.5,
            total_tokens=100,
        )

    monkeypatch.setattr(LLMRouter, "generate_primary_structured", fake_generate_primary)

    run_resp = await client.post(
        "/api/v1/agents/run",
        headers=headers,
        json={
            "request_text": "Find noise cancelling headphones under $300",
            "budget": "300.00",
            "currency": "USD",
            "idempotency_key": "wf-idem-key-0001",
        },
    )
    assert run_resp.status_code == 200, run_resp.text
    workflow = run_resp.json()
    assert workflow["status"] == "AWAITING_USER_APPROVAL"
    assert workflow["current_step"] == "USER_APPROVAL"
    assert len(workflow["discovered_products"]) == 2
    assert workflow["recommendation"]["recommended_product_id"] is not None
    assert workflow["security_assessment"]["can_authorize_payment"] is False
    assert workflow["security_assessment"]["requires_user_approval"] is True

    agent_names = [a["agent_name"] for a in workflow["activities"]]
    for expected_agent in [
        "LEAD_AGENT",
        "DISCOVERY_AGENT",
        "COMPARISON_AGENT",
        "DECISION_AGENT",
        "SECURITY_AGENT",
        "MONITORING_AGENT",
    ]:
        assert expected_agent in agent_names

    # Idempotent repeat returns the exact same workflow ID without duplicating runs
    repeat_resp = await client.post(
        "/api/v1/agents/run",
        headers=headers,
        json={
            "request_text": "Find noise cancelling headphones under $300",
            "budget": "300.00",
            "currency": "USD",
            "idempotency_key": "wf-idem-key-0001",
        },
    )
    assert repeat_resp.status_code == 200
    assert repeat_resp.json()["id"] == workflow["id"]

    # Check status & activity endpoints
    status_resp = await client.get(
        f"/api/v1/agents/status/{workflow['id']}", headers=headers
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "AWAITING_USER_APPROVAL"

    activity_resp = await client.get("/api/v1/agents/activity", headers=headers)
    assert activity_resp.status_code == 200
    assert len(activity_resp.json()) >= 6

    # Cancel workflow
    cancel_resp = await client.post(
        f"/api/v1/agents/cancel/{workflow['id']}", headers=headers
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_security_agent_blocks_when_spending_limit_exceeded(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")
    monkeypatch.setenv("NVIDIA_MODEL", "nvidia/nemotron-test")
    monkeypatch.setenv("ENABLE_TEST_PRODUCT_FIXTURES", "true")
    clear_settings_cache()

    auth = await register_and_login(client, email="lowlimit@example.com")
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    # Lower single transaction limit below test headphone prices (249.00+)
    upd = await client.put(
        "/api/v1/auth/me",
        headers=headers,
        json={"max_single_transaction": "100.00"},
    )
    assert upd.status_code == 200

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
                    "reasoning_summary": "ANC headphones",
                }
            )
        elif name == "_LLMDecisionPayload":
            payload = json.loads(user_prompt)
            obj = schema.model_validate(
                {
                    "recommended_product_id": payload["deterministic_top_product_id"],
                    "recommendation_rationale": "Matches ANC requirement.",
                    "trade_offs": [],
                }
            )
        else:
            payload = json.loads(user_prompt)
            obj = schema.model_validate(
                {
                    "executive_summary": "Blocked due to spending limit.",
                    "recommended_product_id": payload["recommendation"]["recommended_product_id"],
                    "ready_for_user_approval": False,
                    "blocking_reasons": ["Exceeds single-transaction limit"],
                }
            )
        return obj, LLMResponse(
            provider="nvidia_nemotron", model="nvidia/nemotron-test", content="{}", latency_ms=5.0
        )

    monkeypatch.setattr(LLMRouter, "generate_primary_structured", fake_primary)

    run_resp = await client.post(
        "/api/v1/commerce/request",
        headers=headers,
        json={"request_text": "Buy ANC headphones under $300", "budget": "300.00"},
    )
    assert run_resp.status_code == 200
    wf = run_resp.json()
    assert wf["status"] == "BLOCKED_BY_SECURITY"
    assert wf["security_assessment"]["block_execution"] is True
    assert wf["security_assessment"]["can_authorize_payment"] is False

    # Attempting to approve a security-blocked workflow must return 403
    approve_resp = await client.post(
        f"/api/v1/commerce/workflows/{wf['id']}/approve",
        headers=headers,
        json={"confirm_purchase": True, "quantity": 1},
    )
    assert approve_resp.status_code == 403
