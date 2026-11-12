from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import BaseAgent
from app.core.config import Settings, get_settings
from app.core.security import utc_now
from app.llm import LLMError
from app.llm.prompts.security_prompt import SECURITY_SYSTEM_PROMPT
from app.llm.router import LLMRouter, LLMTaskRole
from app.models.order import Order
from app.models.product import Product
from app.models.user import SpendingLimit, User
from app.schemas.payment import PaymentState
from app.services.exchange_rate import ExchangeRateError, ExchangeRateService
from app.utils.currency import (
    calculate_order_total,
    is_paypal_supported_currency,
    quantize_amount,
    validate_currency_code,
)
from app.utils.validators import sanitize_untrusted_text, validate_safe_http_url


class SecurityAssessmentOutput(BaseModel):
    risk_level: str = "LOW"
    risk_score: int = Field(default=10, ge=0, le=100)
    can_authorize_payment: bool = False  # Always False; human + backend controls authorize payments
    requires_user_approval: bool = True
    block_execution: bool = False
    policy_violations: list[str] = Field(default_factory=list)
    anomalies_detected: list[str] = Field(default_factory=list)
    assessment_summary: str = ""
    checked_amount: Decimal
    checked_currency: str
    merchant: str
    within_single_limit: bool = True
    within_daily_limit: bool = True


class _LLMSecurityNotes(BaseModel):
    risk_level: str = "LOW"
    risk_score: int = Field(default=15, ge=0, le=100)
    anomalies_detected: list[str] = Field(default_factory=list)
    assessment_summary: str = ""
    requires_step_up_approval: bool = True


_RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


class SecurityAgent(BaseAgent):
    """Advisory risk assessment and deterministic spending/merchant policy verifier.

    NEVER independently approves or executes payments.
    """

    agent_name = "SECURITY_AGENT"

    def __init__(
        self,
        llm_router: LLMRouter | None = None,
        settings: Settings | None = None,
        exchange_rate_service: ExchangeRateService | None = None,
    ) -> None:
        cfg = settings or get_settings()
        super().__init__(timeout_seconds=cfg.agent_timeout_seconds)
        self.settings = cfg
        self.router = llm_router or LLMRouter(cfg)
        self.exchange_rate_service = exchange_rate_service or ExchangeRateService(cfg)

    async def _sum_allocated_in_currency(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        since: Any,
        target_currency: str,
    ) -> Decimal:
        rows = await session.execute(
            select(Order.currency, func.coalesce(func.sum(Order.amount), 0))
            .where(
                Order.user_id == user_id,
                Order.created_at >= since,
                Order.status.in_(
                    [
                        PaymentState.PENDING_APPROVAL.value,
                        PaymentState.APPROVED.value,
                        PaymentState.CAPTURE_PENDING.value,
                        PaymentState.COMPLETED.value,
                    ]
                ),
            )
            .group_by(Order.currency)
        )
        total = Decimal("0.00")
        for order_currency, subtotal in rows.all():
            amt = Decimal(str(subtotal or "0"))
            if amt <= Decimal("0"):
                continue
            conv = await self.exchange_rate_service.convert_amount(
                amt, order_currency, target_currency
            )
            total += conv.display_amount
        return quantize_amount(total, target_currency)

    async def _run(self, *args: Any, **kwargs: Any) -> tuple[str, SecurityAssessmentOutput]:
        session: AsyncSession = kwargs["session"]
        user: User = kwargs["user"]
        product: Product = kwargs["product"]
        quantity: int = int(kwargs.get("quantity", 1))
        budget: Decimal | None = kwargs.get("budget")
        budget_currency: str = validate_currency_code(
            kwargs.get("budget_currency") or product.currency
        )

        checked_amount = calculate_order_total(product.price, quantity, product.currency)
        violations: list[str] = []
        anomalies: list[str] = []
        risk_score = 10

        # 1. User authorization checks
        if not user.is_active:
            violations.append("User account is inactive.")
            risk_score += 50

        # 2. Product & merchant integrity checks
        if product.availability.upper() == "OUT_OF_STOCK":
            violations.append(f"Product '{product.name}' is currently out of stock.")
            risk_score += 30

        if not product.merchant or not product.merchant.strip():
            violations.append("Merchant metadata is missing.")
            risk_score += 35

        if product.product_url:
            try:
                validate_safe_http_url(product.product_url)
            except ValueError:
                anomalies.append("Product URL has an unusual or invalid scheme.")
                risk_score += 20

        if product.is_test_data and self.settings.app_env == "production":
            violations.append("TEST DATA product cannot be checked out in production.")
            risk_score += 60
        elif product.is_test_data:
            anomalies.append("Product originates from TEST DATA fixtures (non-live inventory).")
            risk_score += 10

        if not is_paypal_supported_currency(product.currency):
            settlement_cur = validate_currency_code(
                self.settings.paypal_settlement_currency
            )
            try:
                settlement_conv = await self.exchange_rate_service.convert_amount(
                    checked_amount, product.currency, settlement_cur
                )
                anomalies.append(
                    f"Merchant currency '{product.currency}' requires verified FX conversion to "
                    f"PayPal settlement currency ({settlement_conv.display_amount} {settlement_cur} "
                    f"at rate {settlement_conv.exchange_rate})."
                )
            except ExchangeRateError as exc:
                violations.append(
                    f"Merchant currency '{product.currency}' is not natively supported by PayPal "
                    f"and cannot be converted safely: {exc}"
                )
                risk_score += 45

        if budget is not None:
            try:
                budget_conv = await self.exchange_rate_service.convert_amount(
                    checked_amount, product.currency, budget_currency
                )
                if budget_conv.display_amount > budget:
                    anomalies.append(
                        f"Order total ({budget_conv.display_amount} {budget_currency} / "
                        f"{checked_amount} {product.currency}) exceeds requested budget "
                        f"({budget} {budget_currency})."
                    )
                    risk_score += 15
            except ExchangeRateError as exc:
                violations.append(
                    f"Unable to verify budget compliance across currencies ({product.currency} -> {budget_currency}): {exc}"
                )
                risk_score += 25

        # 3. Spending limit verification (converted cleanly into spending limit currency)
        limit_res = await session.execute(
            select(SpendingLimit).where(SpendingLimit.user_id == user.id)
        )
        limit = limit_res.scalar_one_or_none()
        within_single = True
        within_daily = True

        if limit is not None:
            limit_cur = validate_currency_code(limit.currency)
            try:
                limit_conv = await self.exchange_rate_service.convert_amount(
                    checked_amount, product.currency, limit_cur
                )
                amt_in_limit = limit_conv.display_amount

                if amt_in_limit > limit.max_single_transaction:
                    within_single = False
                    violations.append(
                        f"Amount {amt_in_limit} {limit_cur} ({checked_amount} {product.currency}) "
                        f"exceeds single-transaction limit ({limit.max_single_transaction} {limit_cur})."
                    )
                    risk_score += 40

                day_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
                spent_today = await self._sum_allocated_in_currency(
                    session,
                    user_id=user.id,
                    since=day_start,
                    target_currency=limit_cur,
                )
                if spent_today + amt_in_limit > limit.daily_limit:
                    within_daily = False
                    violations.append(
                        f"Transaction would exceed daily spending limit ({limit.daily_limit} {limit_cur})."
                    )
                    risk_score += 40

                month_start = utc_now().replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )
                spent_month = await self._sum_allocated_in_currency(
                    session,
                    user_id=user.id,
                    since=month_start,
                    target_currency=limit_cur,
                )
                if spent_month + amt_in_limit > limit.monthly_limit:
                    violations.append(
                        f"Transaction would exceed monthly spending limit ({limit.monthly_limit} {limit_cur})."
                    )
                    risk_score += 40
            except ExchangeRateError as exc:
                within_single = False
                within_daily = False
                violations.append(
                    f"Unable to reconcile order currency '{product.currency}' against spending limit currency "
                    f"'{limit_cur}': {exc}"
                )
                risk_score += 40

        risk_score = min(risk_score, 100)
        if violations:
            risk_level = "CRITICAL" if risk_score >= 75 else "HIGH"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        summary = (
            f"Security assessment: {risk_level} risk (score={risk_score}/100). "
            + (
                f"Blocked due to policy violations: {'; '.join(violations)}"
                if violations
                else "All deterministic policy checks passed; explicit user approval required before checkout."
            )
        )

        # 4. Optional advisory AI analysis via Mistral (never weakens deterministic blocks)
        if self.router.mistral.is_configured():
            try:
                ai_notes, _ = await self.router.generate_supporting_structured(
                    role=LLMTaskRole.STRUCTURED_ANALYSIS,
                    system_prompt=SECURITY_SYSTEM_PROMPT,
                    user_prompt=json.dumps(
                        {
                            "user_active": user.is_active,
                            "product_name": sanitize_untrusted_text(product.name, 200),
                            "merchant": sanitize_untrusted_text(product.merchant, 150),
                            "amount": str(checked_amount),
                            "currency": product.currency,
                            "availability": product.availability,
                            "is_test_data": product.is_test_data,
                            "policy_violations": violations,
                            "anomalies_detected": anomalies,
                            "deterministic_risk_level": risk_level,
                            "deterministic_risk_score": risk_score,
                        }
                    ),
                    schema=_LLMSecurityNotes,
                    temperature=0.0,
                )
                ai_level = ai_notes.risk_level.upper()
                if _RISK_ORDER.get(ai_level, 0) > _RISK_ORDER.get(risk_level, 0):
                    risk_level = ai_level
                risk_score = max(risk_score, ai_notes.risk_score)
                for anomaly in ai_notes.anomalies_detected:
                    if anomaly not in anomalies:
                        anomalies.append(anomaly)
                if ai_notes.assessment_summary.strip() and not violations:
                    summary = ai_notes.assessment_summary.strip()
            except LLMError:
                pass

        output = SecurityAssessmentOutput(
            risk_level=risk_level,
            risk_score=risk_score,
            can_authorize_payment=False,
            requires_user_approval=True,
            block_execution=bool(violations),
            policy_violations=violations,
            anomalies_detected=anomalies,
            assessment_summary=summary,
            checked_amount=checked_amount,
            checked_currency=product.currency,
            merchant=product.merchant,
            within_single_limit=within_single,
            within_daily_limit=within_daily,
        )
        return summary, output

