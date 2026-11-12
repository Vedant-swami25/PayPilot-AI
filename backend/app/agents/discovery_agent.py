from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AgentExecutionError, AgentExecutionStatus, BaseAgent
from app.core.config import Settings, get_settings
from app.llm import LLMError
from app.llm.prompts.discovery_prompt import DISCOVERY_SYSTEM_PROMPT
from app.llm.router import LLMRouter, LLMTaskRole
from app.schemas.product import ProductResponse
from app.services.product_service import ProductService


class DiscoveryQueryRefinement(BaseModel):
    primary_query: str
    fallback_queries: list[str] = Field(default_factory=list)
    max_price: Decimal | None = None
    currency: str = "USD"
    required_attributes: list[str] = Field(default_factory=list)


class DiscoveryOutput(BaseModel):
    query_used: str
    provider: str
    provider_status: str
    is_test_data: bool = False
    products: list[ProductResponse] = Field(default_factory=list)
    limitation: str | None = None


class DiscoveryAgent(BaseAgent):
    """Agent responsible for querying verified product providers without fabricating listings."""

    agent_name = "DISCOVERY_AGENT"

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

    async def _refine_query(
        self,
        search_query: str,
        budget: Decimal | None,
        currency: str,
        specifications: list[str],
    ) -> DiscoveryQueryRefinement:
        if self.router.groq.is_configured():
            try:
                refined, _ = await self.router.generate_supporting_structured(
                    role=LLMTaskRole.FAST_CLASSIFICATION,
                    system_prompt=DISCOVERY_SYSTEM_PROMPT,
                    user_prompt=json.dumps(
                        {
                            "search_query": search_query,
                            "budget": str(budget) if budget is not None else None,
                            "currency": currency,
                            "specifications": specifications,
                        }
                    ),
                    schema=DiscoveryQueryRefinement,
                    temperature=0.0,
                    max_tokens=400,
                )
                return refined
            except LLMError:
                # Non-fatal: fall back to deterministic query from LeadAgent
                pass

        return DiscoveryQueryRefinement(
            primary_query=search_query,
            fallback_queries=[],
            max_price=budget,
            currency=currency,
            required_attributes=specifications,
        )

    async def _run(self, *args: Any, **kwargs: Any) -> tuple[str, DiscoveryOutput]:
        session: AsyncSession = kwargs["session"]
        search_query: str = kwargs["search_query"]
        budget: Decimal | None = kwargs.get("budget")
        currency: str = kwargs.get("currency", "USD")
        specifications: list[str] = kwargs.get("specifications", [])
        limit: int = kwargs.get("limit", 8)

        refinement = await self._refine_query(search_query, budget, currency, specifications)
        queries_to_try = [refinement.primary_query, *refinement.fallback_queries]

        last_result = None
        for candidate_query in queries_to_try:
            try:
                result = await self.product_service.search_products(
                    session,
                    query=candidate_query,
                    max_price=budget,
                    currency=currency,
                    limit=limit,
                )
            except Exception as exc:
                raise AgentExecutionError(
                    f"Product discovery provider failed: {exc}",
                    agent_name=self.agent_name,
                    status=AgentExecutionStatus.FAILED,
                ) from exc

            last_result = result
            if result.provider_status == "NOT_CONFIGURED":
                output = DiscoveryOutput(
                    query_used=candidate_query,
                    provider=result.provider,
                    provider_status=result.provider_status,
                    is_test_data=False,
                    products=[],
                    limitation=result.message,
                )
                raise AgentExecutionError(
                    result.message or "Product provider is not configured.",
                    agent_name=self.agent_name,
                    status=AgentExecutionStatus.NOT_CONFIGURED,
                )

            if result.products:
                output = DiscoveryOutput(
                    query_used=candidate_query,
                    provider=result.provider,
                    provider_status=result.provider_status,
                    is_test_data=result.is_test_data,
                    products=result.products,
                    limitation=result.message,
                )
                summary = (
                    f"Discovered {len(result.products)} products via {result.provider} "
                    f"for query '{candidate_query}'."
                )
                return summary, output

        output = DiscoveryOutput(
            query_used=refinement.primary_query,
            provider=last_result.provider if last_result else "unknown",
            provider_status=last_result.provider_status if last_result else "UNAVAILABLE",
            is_test_data=last_result.is_test_data if last_result else False,
            products=[],
            limitation=(
                last_result.message
                if last_result and last_result.message
                else "No matching products found within constraints."
            ),
        )
        return output.limitation or "No products found.", output

