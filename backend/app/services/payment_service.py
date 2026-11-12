from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Mapping

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.observability import observability
from app.core.security import generate_idempotency_key, utc_now
from app.integrations.paypal.capture import PayPalCaptureAPI
from app.integrations.paypal.client import (
    PayPalClient,
    PayPalError,
    PayPalNotConfiguredError,
)
from app.integrations.paypal.orders import PayPalOrdersAPI
from app.integrations.paypal.webhooks import (
    PayPalWebhooksAPI,
    PayPalWebhookVerificationError,
)
from app.models.agent_activity import CommerceWorkflow
from app.models.order import Order
from app.models.product import Product
from app.models.transaction import Transaction, WebhookEvent
from app.models.user import SpendingLimit, User
from app.schemas.payment import (
    CreateOrderRequest,
    PaymentOrderResponse,
    PaymentQuoteResponse,
    PaymentState,
)
from app.schemas.transaction import WebhookResponse
from app.services.audit_service import AuditService
from app.services.exchange_rate import ExchangeRateError, ExchangeRateService
from app.utils.currency import (
    CurrencyError,
    calculate_order_total,
    is_paypal_supported_currency,
    quantize_amount,
    to_decimal,
    validate_currency_code,
)
from app.utils.helpers import ensure_utc

logger = get_logger(__name__)

_STATE_RANK: dict[str, int] = {
    PaymentState.CREATED.value: 1,
    PaymentState.PENDING_APPROVAL.value: 2,
    PaymentState.APPROVED.value: 3,
    PaymentState.CAPTURE_PENDING.value: 4,
    PaymentState.COMPLETED.value: 5,
    PaymentState.FAILED.value: 5,
    PaymentState.CANCELLED.value: 5,
    PaymentState.REFUNDED.value: 6,
}

_ALLOWED_ACTIONS_BY_STATE: dict[str, list[str]] = {
    PaymentState.CREATED.value: ["create_paypal_order", "cancel"],
    PaymentState.PENDING_APPROVAL.value: ["approve_on_paypal", "sync_status", "cancel"],
    PaymentState.APPROVED.value: ["capture", "cancel", "sync_status"],
    PaymentState.CAPTURE_PENDING.value: ["sync_status"],
    PaymentState.COMPLETED.value: ["view_receipt", "refund"],
    PaymentState.FAILED.value: ["view_details"],
    PaymentState.CANCELLED.value: ["view_details"],
    PaymentState.REFUNDED.value: ["view_receipt"],
}


def get_allowed_actions(payment_status: str) -> list[str]:
    return list(_ALLOWED_ACTIONS_BY_STATE.get(payment_status.upper(), ["view_details"]))


class PaymentService:
    """Backend-authoritative PayPal checkout, state machine, and webhook reconciliation service."""

    def __init__(
        self,
        settings: Settings | None = None,
        paypal_client: PayPalClient | None = None,
        audit_service: AuditService | None = None,
        exchange_rate_service: ExchangeRateService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.paypal_client = paypal_client or PayPalClient(self.settings)
        self.orders_api = PayPalOrdersAPI(self.paypal_client)
        self.capture_api = PayPalCaptureAPI(self.paypal_client)
        self.webhooks_api = PayPalWebhooksAPI(self.paypal_client)
        self.audit = audit_service or AuditService()
        self.exchange_rate_service = exchange_rate_service or ExchangeRateService(
            self.settings
        )

    def _to_response(self, order: Order) -> PaymentOrderResponse:
        snap = order.order_snapshot or {}
        orig_amount = (
            Decimal(str(snap["original_amount"]))
            if snap.get("original_amount") is not None
            else order.amount
        )
        orig_currency = str(snap.get("original_currency") or order.currency)
        disp_amount = (
            Decimal(str(snap["display_amount"]))
            if snap.get("display_amount") is not None
            else orig_amount
        )
        disp_currency = str(snap.get("display_currency") or orig_currency)
        ex_rate = (
            Decimal(str(snap["exchange_rate"]))
            if snap.get("exchange_rate") is not None
            else None
        )
        ex_ts: datetime | None = None
        if snap.get("exchange_rate_timestamp"):
            try:
                ex_ts = datetime.fromisoformat(str(snap["exchange_rate_timestamp"]))
            except ValueError:
                ex_ts = None

        return PaymentOrderResponse(
            id=order.id,
            user_id=order.user_id,
            product_id=order.product_id,
            workflow_id=order.workflow_id,
            paypal_order_id=order.paypal_order_id,
            status=order.status,
            amount=order.amount,
            currency=order.currency,
            quantity=order.quantity,
            merchant=order.merchant,
            approval_status=order.approval_status,
            approval_url=order.approval_url,
            approved_at=order.approved_at,
            allowed_actions=get_allowed_actions(order.status),
            order_snapshot=order.order_snapshot,
            original_amount=orig_amount,
            original_currency=orig_currency,
            display_amount=disp_amount,
            display_currency=disp_currency,
            exchange_rate=ex_rate,
            exchange_rate_timestamp=ex_ts,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )

    async def resolve_checkout_quote(
        self,
        product: Product,
        *,
        quantity: int = 1,
        display_currency: str | None = None,
    ) -> PaymentQuoteResponse:
        """Compute authoritative original, display, and PayPal-payable currency/amount on backend."""
        try:
            orig_currency = validate_currency_code(product.currency)
            disp_currency = (
                validate_currency_code(display_currency)
                if display_currency
                else orig_currency
            )
            orig_unit_price = quantize_amount(product.price, orig_currency)
            orig_amount = calculate_order_total(orig_unit_price, quantity, orig_currency)
        except CurrencyError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        payment_conversion_required = False
        payment_rate = Decimal("1.000000")
        payment_ts: datetime | None = None
        can_checkout = True
        blocking_reason: str | None = None

        if is_paypal_supported_currency(orig_currency):
            payable_currency = orig_currency
            payable_amount = orig_amount
        else:
            payment_conversion_required = True
            settlement_cur = validate_currency_code(
                self.settings.paypal_settlement_currency
            )
            if not is_paypal_supported_currency(settlement_cur):
                return PaymentQuoteResponse(
                    product_id=product.id,
                    product_name=product.name,
                    merchant=product.merchant,
                    quantity=quantity,
                    original_unit_price=orig_unit_price,
                    original_amount=orig_amount,
                    original_currency=orig_currency,
                    display_amount=orig_amount,
                    display_currency=orig_currency,
                    display_exchange_rate=Decimal("1.000000"),
                    payable_amount=orig_amount,
                    payable_currency=orig_currency,
                    payment_conversion_required=True,
                    can_checkout=False,
                    blocking_reason=(
                        f"Merchant currency '{orig_currency}' and settlement currency "
                        f"'{settlement_cur}' are not supported by PayPal checkout."
                    ),
                )
            try:
                pay_conv = await self.exchange_rate_service.convert_amount(
                    orig_amount, orig_currency, settlement_cur
                )
                payable_currency = pay_conv.display_currency
                payable_amount = pay_conv.display_amount
                payment_rate = pay_conv.exchange_rate
                payment_ts = pay_conv.exchange_rate_timestamp
            except ExchangeRateError as exc:
                return PaymentQuoteResponse(
                    product_id=product.id,
                    product_name=product.name,
                    merchant=product.merchant,
                    quantity=quantity,
                    original_unit_price=orig_unit_price,
                    original_amount=orig_amount,
                    original_currency=orig_currency,
                    display_amount=orig_amount,
                    display_currency=orig_currency,
                    display_exchange_rate=Decimal("1.000000"),
                    payable_amount=orig_amount,
                    payable_currency=settlement_cur,
                    payment_conversion_required=True,
                    can_checkout=False,
                    blocking_reason=(
                        f"Cannot reconcile merchant currency '{orig_currency}' to PayPal settlement "
                        f"currency '{settlement_cur}': {exc}"
                    ),
                )

        try:
            disp_conv = await self.exchange_rate_service.convert_amount(
                orig_amount, orig_currency, disp_currency
            )
            display_amount = disp_conv.display_amount
            display_rate = disp_conv.exchange_rate
            display_ts = disp_conv.exchange_rate_timestamp
        except ExchangeRateError as exc:
            display_amount = orig_amount
            disp_currency = orig_currency
            display_rate = Decimal("1.000000")
            display_ts = None
            can_checkout = False
            blocking_reason = (
                f"Live exchange rate unavailable for display currency '{display_currency}': {exc}"
            )

        return PaymentQuoteResponse(
            product_id=product.id,
            product_name=product.name,
            merchant=product.merchant,
            quantity=quantity,
            original_unit_price=orig_unit_price,
            original_amount=orig_amount,
            original_currency=orig_currency,
            display_amount=display_amount,
            display_currency=disp_currency,
            display_exchange_rate=display_rate,
            display_exchange_rate_timestamp=display_ts,
            payable_amount=payable_amount,
            payable_currency=payable_currency,
            payment_conversion_required=payment_conversion_required,
            payment_exchange_rate=payment_rate,
            payment_exchange_rate_timestamp=payment_ts,
            can_checkout=can_checkout,
            blocking_reason=blocking_reason,
        )

    async def get_checkout_quote(
        self,
        session: AsyncSession,
        user: User,
        *,
        product_id: str,
        quantity: int = 1,
        display_currency: str | None = None,
    ) -> PaymentQuoteResponse:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive accounts cannot prepare checkout.",
            )
        prod_res = await session.execute(select(Product).where(Product.id == product_id))
        product = prod_res.scalar_one_or_none()
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected product was not found.",
            )
        return await self.resolve_checkout_quote(
            product,
            quantity=quantity,
            display_currency=display_currency,
        )

    async def _sum_orders_in_currency(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        since: datetime,
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

    async def _enforce_spending_limits(
        self,
        session: AsyncSession,
        user: User,
        amount: Decimal,
        currency: str,
    ) -> None:
        limit_res = await session.execute(
            select(SpendingLimit).where(SpendingLimit.user_id == user.id)
        )
        limit = limit_res.scalar_one_or_none()
        if limit is None:
            return

        limit_cur = validate_currency_code(limit.currency)
        try:
            conv = await self.exchange_rate_service.convert_amount(
                amount, currency, limit_cur
            )
            amt_in_limit = conv.display_amount
            day_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
            spent_today = await self._sum_orders_in_currency(
                session,
                user_id=user.id,
                since=day_start,
                target_currency=limit_cur,
            )
            month_start = utc_now().replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            spent_month = await self._sum_orders_in_currency(
                session,
                user_id=user.id,
                since=month_start,
                target_currency=limit_cur,
            )
        except ExchangeRateError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"Cannot verify spending limit ({limit_cur}) for order in '{currency}' "
                    f"while live exchange rates are unavailable: {exc}"
                ),
            ) from exc

        if amt_in_limit > limit.max_single_transaction:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Order amount {amt_in_limit} {limit_cur} ({amount} {currency}) "
                    f"exceeds single-transaction limit of {limit.max_single_transaction} {limit_cur}."
                ),
            )

        if spent_today + amt_in_limit > limit.daily_limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Order would exceed daily spending limit of {limit.daily_limit} {limit_cur} "
                    f"(already allocated today: {spent_today} {limit_cur})."
                ),
            )

        if spent_month + amt_in_limit > limit.monthly_limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Order would exceed monthly spending limit of {limit.monthly_limit} {limit_cur} "
                    f"(already allocated this month: {spent_month} {limit_cur})."
                ),
            )

    @staticmethod
    def _supports_row_locks(session: AsyncSession) -> bool:
        try:
            bind = session.get_bind()
            return bind is not None and bind.dialect.name != "sqlite"
        except Exception:
            return False

    async def _get_owned_order(
        self,
        session: AsyncSession,
        user_id: str,
        payment_id: str,
        *,
        for_update: bool = False,
    ) -> Order:
        stmt = select(Order).where(
            (Order.id == payment_id) | (Order.paypal_order_id == payment_id)
        )
        if for_update and self._supports_row_locks(session):
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
        order = result.scalar_one_or_none()
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment order not found.",
            )
        if order.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this payment order.",
            )
        return order

    async def create_order(
        self,
        session: AsyncSession,
        user: User,
        payload: CreateOrderRequest,
        *,
        ip_address: str | None = None,
    ) -> PaymentOrderResponse:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive accounts cannot initiate payments.",
            )

        idempotency_key = payload.idempotency_key or generate_idempotency_key("order")

        # 1. Idempotency check
        existing_idem = await session.execute(
            select(Order).where(Order.idempotency_key == idempotency_key)
        )
        existing_order = existing_idem.scalar_one_or_none()
        if existing_order is not None:
            if existing_order.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency key conflict.",
                )
            return self._to_response(existing_order)

        workflow: CommerceWorkflow | None = None
        product_id = payload.product_id
        quantity = payload.quantity

        # 2. Validate workflow approval if workflow_id is provided
        if payload.workflow_id:
            wf_res = await session.execute(
                select(CommerceWorkflow).where(CommerceWorkflow.id == payload.workflow_id)
            )
            workflow = wf_res.scalar_one_or_none()
            if workflow is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Commerce workflow not found.",
                )
            if workflow.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to create payment for this workflow.",
                )
            if workflow.status not in {"APPROVED", "ORDER_CREATED"} or workflow.approved_at is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Workflow must be explicitly approved by the user before creating a PayPal order.",
                )
            if workflow.order_id:
                prior_res = await session.execute(
                    select(Order).where(Order.id == workflow.order_id)
                )
                prior_order = prior_res.scalar_one_or_none()
                if prior_order and prior_order.status not in {
                    PaymentState.CANCELLED.value,
                    PaymentState.FAILED.value,
                }:
                    return self._to_response(prior_order)

            product_id = workflow.approved_product_id

        if not product_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either an approved workflow_id or a valid product_id is required.",
            )

        # 3. Validate product & merchant from persisted database record
        prod_res = await session.execute(select(Product).where(Product.id == product_id))
        product = prod_res.scalar_one_or_none()
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected product was not found.",
            )
        if product.availability.upper() == "OUT_OF_STOCK":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Selected product is currently out of stock.",
            )
        if not product.merchant or not product.merchant.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product merchant information is missing.",
            )
        if product.is_test_data and self.settings.app_env == "production":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TEST DATA products cannot be purchased in production.",
            )

        # 4. Calculate authoritative backend checkout quote & reconciliation
        requested_display_currency = payload.display_currency or (
            workflow.parsed_intent.get("currency")
            if workflow and isinstance(workflow.parsed_intent, dict)
            else None
        )
        quote = await self.resolve_checkout_quote(
            product,
            quantity=quantity,
            display_currency=requested_display_currency,
        )
        if not quote.can_checkout:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=quote.blocking_reason
                or "Order currency and PayPal payment currency cannot be reconciled safely.",
            )

        authoritative_amount = quote.payable_amount
        authoritative_currency = quote.payable_currency

        if not is_paypal_supported_currency(authoritative_currency):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Payment currency '{authoritative_currency}' is not supported by PayPal Orders v2."
                ),
            )

        if workflow is not None and workflow.approved_amount is not None:
            approved_cur = validate_currency_code(
                workflow.approved_currency or authoritative_currency
            )
            approved_amt = quantize_amount(workflow.approved_amount, approved_cur)
            expected_wf_amt = authoritative_amount
            if approved_cur != authoritative_currency:
                try:
                    wf_conv = await self.exchange_rate_service.convert_amount(
                        approved_amt, approved_cur, authoritative_currency
                    )
                    expected_wf_amt = wf_conv.display_amount
                except ExchangeRateError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"Cannot verify approved workflow currency against payment currency: {exc}",
                    ) from exc
            if abs(authoritative_amount - expected_wf_amt) > Decimal("0.01"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Order amount differs from user-approved workflow amount; "
                        "fresh user authorization is required."
                    ),
                )

        if payload.expected_currency is not None:
            submitted_cur = validate_currency_code(payload.expected_currency)
            if submitted_cur != authoritative_currency:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Submitted payment currency '{submitted_cur}' does not match "
                        f"PayPal payable currency '{authoritative_currency}'."
                    ),
                )

        if payload.expected_amount is not None:
            check_cur = (
                validate_currency_code(payload.expected_currency)
                if payload.expected_currency
                else authoritative_currency
            )
            expected_dec = quantize_amount(payload.expected_amount, check_cur)
            if expected_dec != authoritative_amount:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Submitted amount ({expected_dec} {check_cur}) does not match "
                        f"authoritative payable price ({authoritative_amount} {authoritative_currency})."
                    ),
                )

        # 5. Enforce user spending limits
        await self._enforce_spending_limits(
            session, user, authoritative_amount, authoritative_currency
        )

        # 6. Persist initial Order record before calling PayPal
        order = Order(
            user_id=user.id,
            product_id=product.id,
            workflow_id=workflow.id if workflow else None,
            idempotency_key=idempotency_key,
            status=PaymentState.CREATED.value,
            amount=authoritative_amount,
            currency=authoritative_currency,
            quantity=quantity,
            merchant=product.merchant,
            approval_status="PENDING",
            order_snapshot={
                "product_name": product.name,
                "external_product_id": product.external_product_id,
                "unit_price": str(quote.original_unit_price),
                "original_amount": str(quote.original_amount),
                "original_currency": quote.original_currency,
                "display_amount": str(quote.display_amount),
                "display_currency": quote.display_currency,
                "display_exchange_rate": str(quote.display_exchange_rate),
                "display_exchange_rate_timestamp": (
                    quote.display_exchange_rate_timestamp.isoformat()
                    if quote.display_exchange_rate_timestamp
                    else None
                ),
                "payable_amount": str(authoritative_amount),
                "payable_currency": authoritative_currency,
                "payment_conversion_required": quote.payment_conversion_required,
                "exchange_rate": str(
                    quote.payment_exchange_rate
                    if quote.payment_conversion_required
                    else quote.display_exchange_rate
                ),
                "exchange_rate_timestamp": (
                    (
                        quote.payment_exchange_rate_timestamp
                        if quote.payment_conversion_required
                        else quote.display_exchange_rate_timestamp
                    ).isoformat()
                    if (
                        quote.payment_exchange_rate_timestamp
                        if quote.payment_conversion_required
                        else quote.display_exchange_rate_timestamp
                    )
                    else None
                ),
                "quantity": quantity,
                "merchant": product.merchant,
                "is_test_data": product.is_test_data,
            },
        )
        session.add(order)
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            concurrent_res = await session.execute(
                select(Order).where(Order.idempotency_key == idempotency_key)
            )
            concurrent_order = concurrent_res.scalar_one_or_none()
            if concurrent_order is not None and concurrent_order.user_id == user.id:
                return self._to_response(concurrent_order)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Concurrent idempotency key conflict.",
            ) from exc

        # 7. Call PayPal Orders API v2
        fe_base = self.settings.frontend_base_url.rstrip("/")
        try:
            paypal_result = await self.orders_api.create_order(
                reference_id=order.id,
                amount=authoritative_amount,
                currency=authoritative_currency,
                description=f"{product.name} x{quantity} ({product.merchant})",
                idempotency_key=idempotency_key,
                return_url=payload.return_url or f"{fe_base}/checkout/success",
                cancel_url=payload.cancel_url or f"{fe_base}/checkout/cancel",
            )
        except PayPalNotConfiguredError as exc:
            observability.increment("paypal_orders_failed")
            order.status = PaymentState.FAILED.value
            await self.audit.record_audit_log(
                session,
                user_id=user.id,
                action="PAYPAL_ORDER_CREATE_FAILED",
                resource_type="order",
                resource_id=order.id,
                status="NOT_CONFIGURED",
                ip_address=ip_address,
                details={"reason": str(exc)},
            )
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except PayPalError as exc:
            observability.increment("paypal_orders_failed")
            order.status = PaymentState.FAILED.value
            await self.audit.record_audit_log(
                session,
                user_id=user.id,
                action="PAYPAL_ORDER_CREATE_FAILED",
                resource_type="order",
                resource_id=order.id,
                status="FAILURE",
                ip_address=ip_address,
                details={"reason": str(exc)},
            )
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

        order.paypal_order_id = paypal_result.paypal_order_id
        order.approval_url = paypal_result.approval_url
        order.status = (
            PaymentState.APPROVED.value
            if paypal_result.status == "APPROVED"
            else PaymentState.PENDING_APPROVAL.value
        )
        order.approval_status = paypal_result.status

        if workflow is not None:
            workflow.order_id = order.id
            workflow.status = "ORDER_CREATED"
            workflow.current_step = "PAYPAL_CHECKOUT"

        await self.audit.record_audit_log(
            session,
            user_id=user.id,
            action="PAYPAL_ORDER_CREATED",
            resource_type="order",
            resource_id=order.id,
            status="SUCCESS",
            ip_address=ip_address,
            details={
                "paypal_order_id": order.paypal_order_id,
                "amount": str(order.amount),
                "currency": order.currency,
            },
        )
        await session.commit()
        await session.refresh(order)
        observability.increment("paypal_orders_created")
        return self._to_response(order)

    async def get_payment_order(
        self,
        session: AsyncSession,
        user: User,
        payment_id: str,
        *,
        sync_with_paypal: bool = True,
    ) -> PaymentOrderResponse:
        order = await self._get_owned_order(session, user.id, payment_id)

        if (
            sync_with_paypal
            and order.paypal_order_id
            and self.paypal_client.is_configured()
            and order.status
            in {
                PaymentState.CREATED.value,
                PaymentState.PENDING_APPROVAL.value,
                PaymentState.APPROVED.value,
                PaymentState.CAPTURE_PENDING.value,
            }
        ):
            try:
                remote = await self.orders_api.get_order(order.paypal_order_id)
                order.approval_status = remote.status
                if remote.approval_url and not order.approval_url:
                    order.approval_url = remote.approval_url

                if remote.payee_merchant_id or remote.payer_country_code:
                    snap = dict(order.order_snapshot or {})
                    snap_changed = False
                    if (
                        remote.payee_merchant_id
                        and snap.get("paypal_payee_merchant_id") != remote.payee_merchant_id
                    ):
                        snap["paypal_payee_merchant_id"] = remote.payee_merchant_id
                        snap_changed = True
                    if (
                        remote.payer_country_code
                        and snap.get("paypal_payer_country") != remote.payer_country_code
                    ):
                        snap["paypal_payer_country"] = remote.payer_country_code
                        snap_changed = True
                    if (
                        remote.payee_merchant_id
                        and "sandbox" in self.paypal_client.base_url
                        and not snap.get("paypal_merchant_country")
                    ):
                        merchant_info = await self.paypal_client.get_merchant_integration(
                            remote.payee_merchant_id
                        )
                        if merchant_info and merchant_info.get("country"):
                            snap["paypal_merchant_country"] = merchant_info["country"]
                            snap_changed = True
                    if snap_changed:
                        order.order_snapshot = snap

                if remote.status == "APPROVED" and _STATE_RANK[order.status] < 3:
                    order.status = PaymentState.APPROVED.value
                    order.approved_at = order.approved_at or utc_now()
                elif remote.status == "COMPLETED" and _STATE_RANK[order.status] < 5:
                    order.status = PaymentState.COMPLETED.value
                    await self._upsert_transaction(
                        session,
                        order=order,
                        paypal_capture_id=remote.capture_id,
                        tx_status=PaymentState.COMPLETED.value,
                        provider_payload=remote.raw_response,
                    )
                await session.commit()
                await session.refresh(order)
            except PayPalError as exc:
                logger.warning(
                    "paypal_order_sync_failed",
                    order_id=order.id,
                    error=str(exc),
                )

        return self._to_response(order)

    async def _upsert_transaction(
        self,
        session: AsyncSession,
        *,
        order: Order,
        paypal_capture_id: str | None,
        tx_status: str,
        provider_payload: dict[str, Any] | None = None,
        failure_reason: str | None = None,
    ) -> Transaction:
        tx: Transaction | None = None
        if paypal_capture_id:
            res = await session.execute(
                select(Transaction).where(
                    Transaction.paypal_capture_id == paypal_capture_id
                )
            )
            tx = res.scalar_one_or_none()

        if tx is None:
            res = await session.execute(
                select(Transaction).where(Transaction.order_id == order.id)
            )
            tx = res.scalar_one_or_none()

        if tx is None:
            tx = Transaction(
                user_id=order.user_id,
                order_id=order.id,
                paypal_capture_id=paypal_capture_id,
                amount=order.amount,
                currency=order.currency,
                status=tx_status,
                payment_method="paypal",
                provider_payload=provider_payload,
                failure_reason=failure_reason,
            )
            session.add(tx)
        else:
            if paypal_capture_id:
                tx.paypal_capture_id = paypal_capture_id
            tx.status = tx_status
            if provider_payload is not None:
                tx.provider_payload = provider_payload
            if failure_reason is not None:
                tx.failure_reason = failure_reason
        await session.flush()
        return tx

    async def capture_payment(
        self,
        session: AsyncSession,
        user: User,
        payment_id: str,
        *,
        confirm_capture: bool = True,
        ip_address: str | None = None,
    ) -> PaymentOrderResponse:
        if not confirm_capture:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Explicit capture confirmation is required.",
            )

        order = await self._get_owned_order(session, user.id, payment_id, for_update=True)

        if order.status == PaymentState.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order has already been captured and completed.",
            )
        if order.status in {
            PaymentState.CANCELLED.value,
            PaymentState.FAILED.value,
            PaymentState.REFUNDED.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot capture an order in '{order.status}' state.",
            )
        if not order.paypal_order_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order does not have an associated PayPal order ID.",
            )

        # Always verify authoritative order state & amount with PayPal prior to capture
        try:
            remote_order = await self.orders_api.get_order(order.paypal_order_id)
        except PayPalNotConfiguredError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        except PayPalError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc

        if remote_order.amount_value is not None and remote_order.currency_code is not None:
            remote_amt = quantize_amount(remote_order.amount_value, remote_order.currency_code)
            if (
                remote_amt != quantize_amount(order.amount, order.currency)
                or remote_order.currency_code.upper() != order.currency.upper()
            ):
                await self.audit.record_audit_log(
                    session,
                    user_id=user.id,
                    action="PAYPAL_AMOUNT_MISMATCH_BLOCKED",
                    resource_type="order",
                    resource_id=order.id,
                    status="BLOCKED",
                    ip_address=ip_address,
                    details={
                        "local_amount": str(order.amount),
                        "remote_amount": str(remote_amt),
                    },
                )
                await session.commit()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="PayPal order amount mismatch detected; capture aborted.",
                )

        if remote_order.status == "COMPLETED":
            order.status = PaymentState.COMPLETED.value
            order.approval_status = "COMPLETED"
            await self._upsert_transaction(
                session,
                order=order,
                paypal_capture_id=remote_order.capture_id,
                tx_status=PaymentState.COMPLETED.value,
                provider_payload=remote_order.raw_response,
            )
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="PayPal order was already captured.",
            )

        if remote_order.status != "APPROVED":
            order.approval_status = remote_order.status
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Payment cannot be captured until PayPal reports APPROVED "
                    f"(current PayPal status: {remote_order.status})."
                ),
            )

        # User approval verified on PayPal
        order.status = PaymentState.CAPTURE_PENDING.value
        order.approval_status = "APPROVED"
        order.approved_at = order.approved_at or utc_now()
        await session.flush()

        capture_idem_key = f"{order.idempotency_key}-capture"
        try:
            capture_res = await self.capture_api.capture_order(
                paypal_order_id=order.paypal_order_id,
                idempotency_key=capture_idem_key,
            )
        except PayPalError as exc:
            # Timeout / 5xx / transport errors leave PayPal capture outcome uncertain:
            # query PayPal before declaring failure so we never silently mark a captured payment FAILED.
            is_uncertain = exc.status_code is None or exc.status_code >= 500
            if is_uncertain:
                try:
                    reconciled = await self.orders_api.get_order(order.paypal_order_id)
                except PayPalError:
                    reconciled = None

                if reconciled is not None and reconciled.status == "COMPLETED":
                    order.status = PaymentState.COMPLETED.value
                    order.approval_status = "COMPLETED"
                    await self._upsert_transaction(
                        session,
                        order=order,
                        paypal_capture_id=reconciled.capture_id,
                        tx_status=PaymentState.COMPLETED.value,
                        provider_payload=reconciled.raw_response,
                    )
                    if order.workflow_id:
                        wf_res = await session.execute(
                            select(CommerceWorkflow).where(CommerceWorkflow.id == order.workflow_id)
                        )
                        wf = wf_res.scalar_one_or_none()
                        if wf is not None:
                            wf.status = "COMPLETED"
                            wf.current_step = "MONITORING_AGENT"
                    await self.audit.record_audit_log(
                        session,
                        user_id=user.id,
                        action="PAYPAL_CAPTURE_RECONCILED",
                        resource_type="order",
                        resource_id=order.id,
                        status="SUCCESS",
                        ip_address=ip_address,
                        details={
                            "paypal_order_id": order.paypal_order_id,
                            "paypal_capture_id": reconciled.capture_id,
                        },
                    )
                    await session.commit()
                    await session.refresh(order)
                    observability.increment("paypal_captures_succeeded")
                    return self._to_response(order)

                order.status = PaymentState.CAPTURE_PENDING.value
                await self.audit.record_audit_log(
                    session,
                    user_id=user.id,
                    action="PAYPAL_CAPTURE_UNCERTAIN",
                    resource_type="order",
                    resource_id=order.id,
                    status="PENDING",
                    ip_address=ip_address,
                    details={"reason": str(exc)},
                )
                await session.commit()
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Payment capture status is pending confirmation from PayPal. Please refresh before retrying.",
                ) from exc

            observability.increment("paypal_captures_failed")
            order.status = PaymentState.FAILED.value
            await self._upsert_transaction(
                session,
                order=order,
                paypal_capture_id=None,
                tx_status=PaymentState.FAILED.value,
                failure_reason=str(exc),
            )
            await self.audit.record_audit_log(
                session,
                user_id=user.id,
                action="PAYPAL_CAPTURE_FAILED",
                resource_type="order",
                resource_id=order.id,
                status="FAILURE",
                ip_address=ip_address,
                details={"reason": str(exc)},
            )
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc

        cap_status = (capture_res.capture_status or capture_res.order_status).upper()
        if cap_status == "COMPLETED":
            final_status = PaymentState.COMPLETED.value
        elif cap_status == "PENDING":
            final_status = PaymentState.CAPTURE_PENDING.value
        else:
            final_status = PaymentState.FAILED.value

        order.status = final_status
        await self._upsert_transaction(
            session,
            order=order,
            paypal_capture_id=capture_res.paypal_capture_id,
            tx_status=final_status,
            provider_payload=capture_res.raw_response,
            failure_reason=None if final_status != PaymentState.FAILED.value else f"PayPal capture status: {cap_status}",
        )

        if order.workflow_id:
            wf_res = await session.execute(
                select(CommerceWorkflow).where(CommerceWorkflow.id == order.workflow_id)
            )
            wf = wf_res.scalar_one_or_none()
            if wf is not None:
                wf.status = "COMPLETED" if final_status == PaymentState.COMPLETED.value else final_status
                wf.current_step = "MONITORING_AGENT"

        await self.audit.record_audit_log(
            session,
            user_id=user.id,
            action="PAYPAL_CAPTURE_EXECUTED",
            resource_type="order",
            resource_id=order.id,
            status="SUCCESS" if final_status == PaymentState.COMPLETED.value else final_status,
            ip_address=ip_address,
            details={
                "paypal_order_id": order.paypal_order_id,
                "paypal_capture_id": capture_res.paypal_capture_id,
                "final_status": final_status,
            },
        )
        await session.commit()
        await session.refresh(order)
        if final_status == PaymentState.COMPLETED.value:
            observability.increment("paypal_captures_succeeded")
        elif final_status == PaymentState.FAILED.value:
            observability.increment("paypal_captures_failed")
        return self._to_response(order)

    async def refund_payment(
        self,
        session: AsyncSession,
        user: User,
        payment_id: str,
        *,
        reason: str | None = None,
        ip_address: str | None = None,
    ) -> PaymentOrderResponse:
        order = await self._get_owned_order(session, user.id, payment_id, for_update=True)

        if order.status == PaymentState.REFUNDED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order has already been refunded.",
            )
        if order.status != PaymentState.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only COMPLETED orders can be refunded (current state: '{order.status}').",
            )

        tx_res = await session.execute(
            select(Transaction).where(Transaction.order_id == order.id)
        )
        tx = tx_res.scalar_one_or_none()
        if tx is None or not tx.paypal_capture_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order does not have a recorded PayPal capture ID to refund.",
            )

        refund_idem_key = f"{order.idempotency_key}-refund"
        try:
            refund_res = await self.capture_api.refund_capture(
                capture_id=tx.paypal_capture_id,
                idempotency_key=refund_idem_key,
                amount=quantize_amount(order.amount, order.currency),
                currency=order.currency,
                note_to_payer=reason,
            )
        except PayPalNotConfiguredError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        except PayPalError as exc:
            observability.increment("paypal_refunds_failed")
            await self.audit.record_audit_log(
                session,
                user_id=user.id,
                action="PAYPAL_REFUND_FAILED",
                resource_type="order",
                resource_id=order.id,
                status="FAILURE",
                ip_address=ip_address,
                details={"reason": str(exc), "paypal_capture_id": tx.paypal_capture_id},
            )
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc

        if refund_res.status != "COMPLETED":
            observability.increment("paypal_refunds_failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"PayPal refund returned non-completed status: {refund_res.status}",
            )

        order.status = PaymentState.REFUNDED.value
        await self._upsert_transaction(
            session,
            order=order,
            paypal_capture_id=tx.paypal_capture_id,
            tx_status=PaymentState.REFUNDED.value,
            provider_payload=refund_res.raw_response,
            failure_reason=reason or "Refunded by user",
        )

        if order.workflow_id:
            wf_res = await session.execute(
                select(CommerceWorkflow).where(CommerceWorkflow.id == order.workflow_id)
            )
            wf = wf_res.scalar_one_or_none()
            if wf is not None:
                wf.status = "REFUNDED"
                wf.current_step = "REFUNDED"

        await self.audit.record_audit_log(
            session,
            user_id=user.id,
            action="PAYPAL_CAPTURE_REFUNDED",
            resource_type="order",
            resource_id=order.id,
            status="SUCCESS",
            ip_address=ip_address,
            details={
                "paypal_capture_id": tx.paypal_capture_id,
                "paypal_refund_id": refund_res.paypal_refund_id,
                "reason": reason,
            },
        )
        await session.commit()
        await session.refresh(order)
        observability.increment("paypal_refunds_succeeded")
        return self._to_response(order)

    async def cancel_payment(
        self,
        session: AsyncSession,
        user: User,
        payment_id: str,
        *,
        reason: str | None = None,
        ip_address: str | None = None,
    ) -> PaymentOrderResponse:
        order = await self._get_owned_order(session, user.id, payment_id)

        if order.status not in {
            PaymentState.CREATED.value,
            PaymentState.PENDING_APPROVAL.value,
            PaymentState.APPROVED.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Order in state '{order.status}' cannot be cancelled.",
            )

        order.status = PaymentState.CANCELLED.value
        order.approval_status = "CANCELLED"
        await self._upsert_transaction(
            session,
            order=order,
            paypal_capture_id=None,
            tx_status=PaymentState.CANCELLED.value,
            failure_reason=reason or "Cancelled by user",
        )

        if order.workflow_id:
            wf_res = await session.execute(
                select(CommerceWorkflow).where(CommerceWorkflow.id == order.workflow_id)
            )
            wf = wf_res.scalar_one_or_none()
            if wf is not None and wf.status not in {"COMPLETED", "CANCELLED"}:
                wf.status = "CANCELLED"

        await self.audit.record_audit_log(
            session,
            user_id=user.id,
            action="PAYMENT_ORDER_CANCELLED",
            resource_type="order",
            resource_id=order.id,
            status="SUCCESS",
            ip_address=ip_address,
            details={"reason": reason},
        )
        await session.commit()
        await session.refresh(order)
        return self._to_response(order)

    async def process_paypal_webhook(
        self,
        session: AsyncSession,
        *,
        headers: Mapping[str, str],
        event_payload: dict[str, Any],
        ip_address: str | None = None,
    ) -> WebhookResponse:
        event_id = str(event_payload.get("id") or "").strip()
        event_type = str(event_payload.get("event_type") or "").strip()
        if not event_id or not event_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook payload must include 'id' and 'event_type'.",
            )

        # 1. Verify PayPal signature BEFORE mutating or trusting any event state
        try:
            verified = await self.webhooks_api.verify_signature(
                headers=headers, webhook_event=event_payload
            )
        except PayPalWebhookVerificationError as exc:
            status_code = (
                status.HTTP_503_SERVICE_UNAVAILABLE
                if exc.status_code == 503
                else status.HTTP_400_BAD_REQUEST
            )
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc
        except PayPalError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc

        if not verified:
            observability.increment("webhooks_rejected")
            await self.audit.record_audit_log(
                session,
                user_id=None,
                action="PAYPAL_WEBHOOK_SIGNATURE_INVALID",
                resource_type="webhook_event",
                resource_id=event_id,
                status="BLOCKED",
                ip_address=ip_address,
                details={"event_type": event_type},
            )
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="PayPal webhook signature verification failed.",
            )

        # 2. Idempotency check
        existing_res = await session.execute(
            select(WebhookEvent).where(WebhookEvent.paypal_event_id == event_id)
        )
        existing_event = existing_res.scalar_one_or_none()
        if existing_event is not None:
            observability.increment("webhooks_duplicate")
            return WebhookResponse(
                received=True,
                event_id=event_id,
                event_type=event_type,
                status=existing_event.processing_status,
                duplicate=True,
                details={"message": "Duplicate webhook event ignored idempotently."},
            )

        resource = event_payload.get("resource") or {}
        if not isinstance(resource, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook 'resource' must be a JSON object.",
            )

        resource_id = resource.get("id")
        related_ids = (
            (resource.get("supplementary_data") or {}).get("related_ids") or {}
        )
        paypal_order_id = (
            resource_id
            if event_type.startswith("CHECKOUT.ORDER.")
            else related_ids.get("order_id")
        )
        paypal_capture_id = (
            resource_id
            if event_type.startswith("PAYMENT.CAPTURE.")
            else None
        )
        if event_type in {"PAYMENT.CAPTURE.REFUNDED", "PAYMENT.CAPTURE.REVERSED"}:
            # Refund resources link back to capture or order via links/supplementary_data
            paypal_capture_id = related_ids.get("capture_id") or paypal_capture_id

        webhook_record = WebhookEvent(
            paypal_event_id=event_id,
            event_type=event_type,
            resource_id=str(resource_id) if resource_id else None,
            paypal_order_id=str(paypal_order_id) if paypal_order_id else None,
            paypal_capture_id=str(paypal_capture_id) if paypal_capture_id else None,
            verification_status="SUCCESS",
            processing_status="RECEIVED",
            payload=event_payload,
        )
        session.add(webhook_record)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            observability.increment("webhooks_duplicate")
            dup_res = await session.execute(
                select(WebhookEvent).where(WebhookEvent.paypal_event_id == event_id)
            )
            dup_event = dup_res.scalar_one_or_none()
            return WebhookResponse(
                received=True,
                event_id=event_id,
                event_type=event_type,
                status=dup_event.processing_status if dup_event else "PROCESSED",
                duplicate=True,
                details={"message": "Concurrent duplicate webhook event ignored idempotently."},
            )

        # 3. Locate matching Order safely (with row lock on PostgreSQL)
        order: Order | None = None
        if paypal_order_id:
            stmt = select(Order).where(Order.paypal_order_id == str(paypal_order_id))
            if self._supports_row_locks(session):
                stmt = stmt.with_for_update()
            order_res = await session.execute(stmt)
            order = order_res.scalar_one_or_none()
        if order is None and paypal_capture_id:
            tx_res = await session.execute(
                select(Transaction).where(
                    Transaction.paypal_capture_id == str(paypal_capture_id)
                )
            )
            tx = tx_res.scalar_one_or_none()
            if tx is not None:
                stmt = select(Order).where(Order.id == tx.order_id)
                if self._supports_row_locks(session):
                    stmt = stmt.with_for_update()
                order_res = await session.execute(stmt)
                order = order_res.scalar_one_or_none()

        if order is None:
            webhook_record.processing_status = "UNMATCHED"
            webhook_record.processed_at = utc_now()
            await session.commit()
            return WebhookResponse(
                received=True,
                event_id=event_id,
                event_type=event_type,
                status="UNMATCHED",
                duplicate=False,
                details={"message": "No local order matched this verified webhook event."},
            )

        # 4. Validate amount if present on resource before completing
        resource_amount = resource.get("amount")
        if isinstance(resource_amount, dict) and resource_amount.get("value") is not None:
            res_cur = str(resource_amount.get("currency_code") or order.currency).upper()
            res_val = quantize_amount(to_decimal(resource_amount["value"], allow_zero=True), res_cur)
            if (
                event_type == "PAYMENT.CAPTURE.COMPLETED"
                and (
                    res_cur != order.currency.upper()
                    or res_val != quantize_amount(order.amount, order.currency)
                )
            ):
                webhook_record.processing_status = "AMOUNT_MISMATCH_BLOCKED"
                webhook_record.error_message = (
                    f"Webhook amount {res_val} {res_cur} != Order amount {order.amount} {order.currency}"
                )
                webhook_record.processed_at = utc_now()
                await self.audit.record_audit_log(
                    session,
                    user_id=order.user_id,
                    action="PAYPAL_WEBHOOK_AMOUNT_MISMATCH",
                    resource_type="order",
                    resource_id=order.id,
                    status="BLOCKED",
                    ip_address=ip_address,
                    details={"event_id": event_id},
                )
                observability.increment("webhooks_rejected")
                await session.commit()
                return WebhookResponse(
                    received=True,
                    event_id=event_id,
                    event_type=event_type,
                    status="BLOCKED",
                    duplicate=False,
                )

        # 5. Apply monotonic state transitions safely (out-of-order protection)
        current_rank = _STATE_RANK.get(order.status, 0)
        new_status: str | None = None

        if event_type == "CHECKOUT.ORDER.APPROVED":
            if current_rank < _STATE_RANK[PaymentState.APPROVED.value]:
                new_status = PaymentState.APPROVED.value
                order.approval_status = "APPROVED"
                order.approved_at = order.approved_at or utc_now()
        elif event_type == "PAYMENT.CAPTURE.PENDING":
            if current_rank < _STATE_RANK[PaymentState.CAPTURE_PENDING.value]:
                new_status = PaymentState.CAPTURE_PENDING.value
        elif event_type == "PAYMENT.CAPTURE.COMPLETED":
            if order.status != PaymentState.REFUNDED.value:
                new_status = PaymentState.COMPLETED.value
                order.approval_status = "COMPLETED"
        elif event_type == "PAYMENT.CAPTURE.DENIED":
            if current_rank < _STATE_RANK[PaymentState.COMPLETED.value]:
                new_status = PaymentState.FAILED.value
        elif event_type in {"PAYMENT.CAPTURE.REFUNDED", "PAYMENT.CAPTURE.REVERSED"}:
            new_status = PaymentState.REFUNDED.value

        if new_status is not None:
            order.status = new_status
            await self._upsert_transaction(
                session,
                order=order,
                paypal_capture_id=str(paypal_capture_id) if paypal_capture_id else None,
                tx_status=new_status,
                provider_payload=event_payload,
            )
            webhook_record.processing_status = "PROCESSED"
        else:
            webhook_record.processing_status = "IGNORED_OUT_OF_ORDER"

        webhook_record.processed_at = utc_now()
        await self.audit.record_audit_log(
            session,
            user_id=order.user_id,
            action=f"PAYPAL_WEBHOOK_{event_type}",
            resource_type="order",
            resource_id=order.id,
            status=webhook_record.processing_status,
            ip_address=ip_address,
            details={"event_id": event_id, "order_status": order.status},
        )
        observability.increment("webhooks_processed")
        await session.commit()

        return WebhookResponse(
            received=True,
            event_id=event_id,
            event_type=event_type,
            status=webhook_record.processing_status,
            duplicate=False,
            details={"order_id": order.id, "order_status": order.status},
        )

