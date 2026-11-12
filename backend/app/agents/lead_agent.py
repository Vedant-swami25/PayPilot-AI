from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.agents import AgentExecutionError, AgentExecutionStatus, BaseAgent
from app.core.config import Settings, get_settings
from app.llm import LLMError, LLMNotConfiguredError, LLMTimeoutError
from app.llm.prompts.lead_prompt import LEAD_SYNTHESIS_PROMPT, LEAD_SYSTEM_PROMPT
from app.llm.router import LLMRouter
from app.utils.currency import quantize_amount, to_decimal, validate_currency_code


class ExecutionPlanStep(BaseModel):
    step: str
    goal: str


class LeadPlanOutput(BaseModel):
    search_query: str
    category: str | None = None
    budget: Decimal | None = None
    currency: str = "USD"
    specifications: list[str] = Field(default_factory=list)
    brand_preferences: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    execution_plan: list[ExecutionPlanStep] = Field(default_factory=list)
    reasoning_summary: str = ""
    provider: str = "nvidia_nemotron"
    model: str | None = None


class LeadSynthesisOutput(BaseModel):
    executive_summary: str
    recommended_product_id: str | None = None
    ready_for_user_approval: bool
    blocking_reasons: list[str] = Field(default_factory=list)


class LeadAgent(BaseAgent):
    """Primary orchestrating reasoning agent powered strictly by NVIDIA Nemotron."""

    agent_name = "LEAD_AGENT"

    def __init__(
        self,
        llm_router: LLMRouter | None = None,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        super().__init__(timeout_seconds=cfg.agent_timeout_seconds)
        self.settings = cfg
        self.router = llm_router or LLMRouter(cfg)

    async def _run(self, *args: Any, **kwargs: Any) -> tuple[str, Any]:
        mode = kwargs.get("mode", "plan")
        if mode == "synthesize":
            return await self._synthesize(
                request_text=kwargs["request_text"],
                discovery_summary=kwargs["discovery_summary"],
                comparison_summary=kwargs["comparison_summary"],
                recommendation=kwargs["recommendation"],
                security_assessment=kwargs["security_assessment"],
            )
        return await self._plan(
            request_text=kwargs["request_text"],
            explicit_budget=kwargs.get("explicit_budget"),
            explicit_currency=kwargs.get("explicit_currency"),
        )

    async def _plan(
        self,
        *,
        request_text: str,
        explicit_budget: Decimal | None = None,
        explicit_currency: str | None = None,
    ) -> tuple[str, LeadPlanOutput]:
        prompt_payload = {
            "user_request": request_text,
            "explicit_budget": str(explicit_budget) if explicit_budget is not None else None,
            "explicit_currency": explicit_currency or self.settings.default_currency,
        }

        try:
            plan, llm_resp = await self.router.generate_primary_structured(
                system_prompt=LEAD_SYSTEM_PROMPT,
                user_prompt=json.dumps(prompt_payload),
                schema=LeadPlanOutput,
                temperature=0.1,
            )
        except LLMNotConfiguredError as exc:
            raise AgentExecutionError(
                str(exc),
                agent_name=self.agent_name,
                status=AgentExecutionStatus.NOT_CONFIGURED,
            ) from exc
        except LLMTimeoutError as exc:
            raise AgentExecutionError(
                str(exc),
                agent_name=self.agent_name,
                status=AgentExecutionStatus.TIMED_OUT,
            ) from exc
        except LLMError as exc:
            raise AgentExecutionError(
                f"Primary reasoning model (NVIDIA Nemotron) unavailable: {exc}",
                agent_name=self.agent_name,
                status=AgentExecutionStatus.FAILED,
            ) from exc

        # Enforce explicit API constraints and normalize currency/budget
        currency = validate_currency_code(
            explicit_currency or plan.currency or self.settings.default_currency
        )
        plan.currency = currency
        if explicit_budget is not None:
            plan.budget = quantize_amount(explicit_budget, currency)
        elif plan.budget is not None:
            plan.budget = quantize_amount(to_decimal(plan.budget), currency)

        if not plan.search_query.strip():
            plan.search_query = request_text.strip()[:120]

        if not plan.execution_plan:
            plan.execution_plan = [
                ExecutionPlanStep(step="DISCOVERY_AGENT", goal="Search verified product providers"),
                ExecutionPlanStep(step="COMPARISON_AGENT", goal="Calculate price and spec differences"),
                ExecutionPlanStep(step="DECISION_AGENT", goal="Rank best-fit recommendation"),
                ExecutionPlanStep(step="SECURITY_AGENT", goal="Evaluate limits and transaction risk"),
            ]

        plan.provider = llm_resp.provider
        plan.model = llm_resp.model
        summary = (
            f"Nemotron parsed request for '{plan.search_query}' "
            f"(budget={plan.budget} {plan.currency}, specs={len(plan.specifications)})."
        )
        return summary, plan

    async def _synthesize(
        self,
        *,
        request_text: str,
        discovery_summary: dict[str, Any],
        comparison_summary: dict[str, Any] | None,
        recommendation: dict[str, Any] | None,
        security_assessment: dict[str, Any],
    ) -> tuple[str, LeadSynthesisOutput]:
        prompt_payload = {
            "user_request": request_text,
            "discovery": discovery_summary,
            "comparison": comparison_summary,
            "recommendation": recommendation,
            "security": security_assessment,
        }
        try:
            synthesis, _ = await self.router.generate_primary_structured(
                system_prompt=LEAD_SYNTHESIS_PROMPT,
                user_prompt=json.dumps(prompt_payload, default=str),
                schema=LeadSynthesisOutput,
                temperature=0.1,
            )
        except LLMNotConfiguredError as exc:
            raise AgentExecutionError(
                str(exc),
                agent_name=self.agent_name,
                status=AgentExecutionStatus.NOT_CONFIGURED,
            ) from exc
        except LLMError as exc:
            raise AgentExecutionError(
                f"NVIDIA Nemotron synthesis failed: {exc}",
                agent_name=self.agent_name,
                status=AgentExecutionStatus.FAILED,
            ) from exc

        # Enforce deterministic security blocking rules even if LLM suggests otherwise
        if security_assessment.get("block_execution"):
            synthesis.ready_for_user_approval = False
            for violation in security_assessment.get("policy_violations", []):
                if violation not in synthesis.blocking_reasons:
                    synthesis.blocking_reasons.append(violation)

        return synthesis.executive_summary, synthesis

