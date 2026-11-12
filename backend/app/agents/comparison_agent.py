from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.agents import BaseAgent
from app.core.config import Settings, get_settings
from app.llm import LLMError
from app.llm.prompts.comparison_prompt import COMPARISON_SYSTEM_PROMPT
from app.llm.router import LLMRouter, LLMTaskRole
from app.models.product import Product
from app.schemas.product import ProductComparisonItem, ProductComparisonResponse
from app.services.product_service import ProductService
from app.utils.validators import sanitize_untrusted_text


class _MistralEvalItem(BaseModel):
    product_id: str
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)


class _MistralComparisonNotes(BaseModel):
    evaluations: list[_MistralEvalItem] = Field(default_factory=list)


class ComparisonAgent(BaseAgent):
    """Agent performing deterministic Decimal price/spec comparison plus grounded qualitative analysis."""

    agent_name = "COMPARISON_AGENT"

    def __init__(
        self,
        product_service: ProductService | None = None,
        llm_router: LLMRouter | None = None,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        super().__init__(timeout_seconds=cfg.agent_timeout_seconds)
        self.settings = cfg
        self.product_service = product_service or ProductService(cfg)
        self.router = llm_router or LLMRouter(cfg)

    async def _run(self, *args: Any, **kwargs: Any) -> tuple[str, ProductComparisonResponse]:
        products: list[Product] = kwargs["products"]
        budget: Decimal | None = kwargs.get("budget")
        currency: str | None = kwargs.get("currency")
        requirements: list[str] = kwargs.get("requirements", [])

        if not products:
            raise ValueError("Cannot compare an empty product list.")

        if len(products) == 1:
            p = products[0]
            converted = await self.product_service.to_product_response(
                p, target_currency=currency
            )
            eff_price = converted.display_price or converted.price
            eff_currency = converted.display_currency or converted.currency
            within_budget = (eff_price <= budget) if budget is not None else None
            single_item = ProductComparisonItem(
                product_id=p.id,
                external_product_id=p.external_product_id,
                name=p.name,
                merchant=p.merchant,
                price=eff_price,
                currency=eff_currency,
                original_price=converted.original_price,
                original_currency=converted.original_currency,
                display_price=converted.display_price,
                display_currency=converted.display_currency,
                exchange_rate=converted.exchange_rate,
                exchange_rate_timestamp=converted.exchange_rate_timestamp,
                availability=p.availability,
                price_delta_from_lowest=Decimal("0.00"),
                price_delta_percent=Decimal("0.00"),
                within_budget=within_budget,
                requirement_match_score=Decimal("100.00"),
                pros=["Only matching candidate retrieved from provider"],
                cons=(
                    ["No competing products available for multi-option comparison"]
                    + (["Marked as TEST DATA"] if p.is_test_data else [])
                ),
                specifications=p.specifications or {},
            )
            comparison = ProductComparisonResponse(
                currency=eff_currency,
                lowest_price=eff_price,
                highest_price=eff_price,
                average_price=eff_price,
                price_spread=Decimal("0.00"),
                best_value_product_id=p.id,
                items=[single_item],
                summary=f"Single candidate evaluated: {p.name} at {eff_price} {eff_currency}.",
                exchange_rate=converted.exchange_rate,
                exchange_rate_timestamp=converted.exchange_rate_timestamp,
            )
            return comparison.summary, comparison

        # 1. Deterministic calculations always run first (with consistent currency conversion)
        comparison = await self.product_service.compare_product_records_async(
            products,
            budget=budget,
            target_currency=currency,
            requirements=requirements,
        )

        # 2. Optional Mistral enrichment strictly constrained to retrieved product IDs
        if self.router.mistral.is_configured():
            try:
                compact_items = []
                for c_item in comparison.items:
                    specs = c_item.specifications or {}
                    compact_items.append(
                        {
                            "product_id": c_item.product_id,
                            "name": sanitize_untrusted_text(c_item.name, 140),
                            "merchant": sanitize_untrusted_text(c_item.merchant, 100),
                            "price": str(c_item.price),
                            "currency": c_item.currency,
                            "availability": c_item.availability,
                            "within_budget": c_item.within_budget,
                            "requirement_match_score": str(c_item.requirement_match_score),
                            "brand": sanitize_untrusted_text(str(specs.get("brand") or ""), 60),
                            "key_features": [
                                sanitize_untrusted_text(str(f), 80)
                                for f in (specs.get("key_features") or [])[:3]
                            ],
                        }
                    )
                notes, _ = await self.router.generate_supporting_structured(
                    role=LLMTaskRole.STRUCTURED_ANALYSIS,
                    system_prompt=COMPARISON_SYSTEM_PROMPT,
                    user_prompt=json.dumps(
                        {
                            "requirements": [sanitize_untrusted_text(r, 120) for r in requirements],
                            "budget": str(budget) if budget is not None else None,
                            "candidates": compact_items,
                        }
                    ),
                    schema=_MistralComparisonNotes,
                    temperature=0.1,
                    max_tokens=1800,
                )
                valid_ids = {item.product_id for item in comparison.items}
                eval_by_id = {
                    ev.product_id: ev
                    for ev in notes.evaluations
                    if ev.product_id in valid_ids
                }
                for item in comparison.items:
                    ev = eval_by_id.get(item.product_id)
                    if ev:
                        for pro in ev.pros[:3]:
                            if pro not in item.pros:
                                item.pros.append(pro)
                        for con in ev.cons[:3]:
                            if con not in item.cons:
                                item.cons.append(con)
            except LLMError:
                # Deterministic comparison remains authoritative and complete
                pass

        return comparison.summary, comparison

