from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.agents import AgentExecutionError, AgentExecutionStatus, BaseAgent
from app.core.config import Settings, get_settings
from app.llm import LLMError, LLMNotConfiguredError
from app.llm.prompts.comparison_prompt import DECISION_SYSTEM_PROMPT
from app.llm.router import LLMRouter
from app.schemas.product import ProductComparisonResponse
from app.utils.validators import sanitize_untrusted_text


class RankedOption(BaseModel):
    rank: int
    product_id: str
    name: str
    merchant: str
    price: Decimal
    currency: str
    original_price: Decimal | None = None
    original_currency: str | None = None
    display_price: Decimal | None = None
    display_currency: str | None = None
    exchange_rate: Decimal | None = None
    exchange_rate_timestamp: datetime | None = None
    availability: str
    within_budget: bool | None = None
    requirement_match_score: Decimal


class DecisionOutput(BaseModel):
    recommended_product_id: str
    recommended_product_name: str
    recommended_price: Decimal
    currency: str
    original_price: Decimal | None = None
    original_currency: str | None = None
    display_price: Decimal | None = None
    display_currency: str | None = None
    exchange_rate: Decimal | None = None
    exchange_rate_timestamp: datetime | None = None
    merchant: str
    rationale: str
    trade_offs: list[str] = Field(default_factory=list)
    ranked_options: list[RankedOption] = Field(default_factory=list)


class _LLMDecisionPayload(BaseModel):
    recommended_product_id: str
    recommendation_rationale: str
    trade_offs: list[str] = Field(default_factory=list)


class DecisionAgent(BaseAgent):
    """Agent that ranks compared products and explains grounded purchase recommendations."""

    agent_name = "DECISION_AGENT"

    def __init__(
        self,
        llm_router: LLMRouter | None = None,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        super().__init__(timeout_seconds=cfg.agent_timeout_seconds)
        self.settings = cfg
        self.router = llm_router or LLMRouter(cfg)

    async def _run(self, *args: Any, **kwargs: Any) -> tuple[str, DecisionOutput]:
        comparison: ProductComparisonResponse = kwargs["comparison"]
        user_request: str = kwargs["request_text"]

        if not comparison.items:
            raise AgentExecutionError(
                "No products available for recommendation.",
                agent_name=self.agent_name,
                status=AgentExecutionStatus.FAILED,
            )

        sorted_items = sorted(
            comparison.items,
            key=lambda item: (
                1 if item.availability.upper() == "IN_STOCK" else 0,
                1 if item.within_budget is not False else 0,
                item.requirement_match_score,
                -item.price,
            ),
            reverse=True,
        )

        ranked_options = [
            RankedOption(
                rank=idx + 1,
                product_id=item.product_id,
                name=item.name,
                merchant=item.merchant,
                price=item.price,
                currency=item.currency,
                original_price=item.original_price,
                original_currency=item.original_currency,
                display_price=item.display_price or item.price,
                display_currency=item.display_currency or item.currency,
                exchange_rate=item.exchange_rate,
                exchange_rate_timestamp=item.exchange_rate_timestamp,
                availability=item.availability,
                within_budget=item.within_budget,
                requirement_match_score=item.requirement_match_score,
            )
            for idx, item in enumerate(sorted_items)
        ]

        deterministic_top = sorted_items[0]
        valid_ids = {item.product_id for item in sorted_items}
        selected_item = deterministic_top
        rationale = (
            f"Recommended '{deterministic_top.name}' from {deterministic_top.merchant} "
            f"at {deterministic_top.price} {deterministic_top.currency} based on availability "
            f"({deterministic_top.availability}), budget compliance, and requirement match score "
            f"({deterministic_top.requirement_match_score}%)."
        )
        trade_offs: list[str] = []

        # Use primary reasoning model (Nemotron) to synthesize grounded trade-offs
        try:
            compact_candidates = [
                {
                    "product_id": item.product_id,
                    "name": sanitize_untrusted_text(item.name, 140),
                    "merchant": sanitize_untrusted_text(item.merchant, 100),
                    "price": str(item.price),
                    "currency": item.currency,
                    "availability": item.availability,
                    "within_budget": item.within_budget,
                    "requirement_match_score": str(item.requirement_match_score),
                    "pros": item.pros[:2],
                    "cons": item.cons[:2],
                }
                for item in sorted_items[:8]
            ]
            llm_decision, _ = await self.router.generate_primary_structured(
                system_prompt=DECISION_SYSTEM_PROMPT,
                user_prompt=json.dumps(
                    {
                        "user_request": sanitize_untrusted_text(user_request, 300),
                        "currency": comparison.currency,
                        "lowest_price": str(comparison.lowest_price),
                        "highest_price": str(comparison.highest_price),
                        "deterministic_top_product_id": deterministic_top.product_id,
                        "candidates": compact_candidates,
                    }
                ),
                schema=_LLMDecisionPayload,
                temperature=0.1,
                max_tokens=1600,
            )
            if llm_decision.recommended_product_id in valid_ids:
                candidate = next(
                    item
                    for item in sorted_items
                    if item.product_id == llm_decision.recommended_product_id
                )
                # Guard against recommending an out-of-stock or over-budget item when a valid one exists
                if candidate.availability.upper() == "IN_STOCK" and (
                    candidate.within_budget is not False
                    or deterministic_top.within_budget is False
                ):
                    selected_item = candidate
            if llm_decision.recommendation_rationale.strip():
                rationale = llm_decision.recommendation_rationale.strip()
            trade_offs = llm_decision.trade_offs
        except LLMNotConfiguredError as exc:
            raise AgentExecutionError(
                str(exc),
                agent_name=self.agent_name,
                status=AgentExecutionStatus.NOT_CONFIGURED,
            ) from exc
        except LLMError as exc:
            raise AgentExecutionError(
                f"NVIDIA Nemotron decision reasoning failed: {exc}",
                agent_name=self.agent_name,
                status=AgentExecutionStatus.FAILED,
            ) from exc

        output = DecisionOutput(
            recommended_product_id=selected_item.product_id,
            recommended_product_name=selected_item.name,
            recommended_price=selected_item.price,
            currency=selected_item.currency,
            original_price=selected_item.original_price,
            original_currency=selected_item.original_currency,
            display_price=selected_item.display_price or selected_item.price,
            display_currency=selected_item.display_currency or selected_item.currency,
            exchange_rate=selected_item.exchange_rate,
            exchange_rate_timestamp=selected_item.exchange_rate_timestamp,
            merchant=selected_item.merchant,
            rationale=rationale,
            trade_offs=trade_offs,
            ranked_options=ranked_options,
        )
        summary = (
            f"Recommended {output.recommended_product_name} "
            f"({output.recommended_price} {output.currency} from {output.merchant})."
        )
        return summary, output

