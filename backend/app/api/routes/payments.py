from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_payment_service
from app.core.database import get_db
from app.core.security import get_client_ip
from app.models.user import User
from app.schemas.payment import (
    CancelPaymentRequest,
    CapturePaymentRequest,
    CreateOrderRequest,
    PaymentOrderResponse,
    PaymentQuoteResponse,
    RefundPaymentRequest,
)
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments (PayPal)"])


@router.get(
    "/quote",
    response_model=PaymentQuoteResponse,
    summary="Compute backend-authoritative checkout totals across original, display, and PayPal currencies",
)
async def get_checkout_quote(
    product_id: str = Query(..., min_length=1),
    quantity: int = Query(default=1, ge=1, le=20),
    display_currency: str | None = Query(default=None, min_length=3, max_length=3),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    payment_service: PaymentService = Depends(get_payment_service),
) -> PaymentQuoteResponse:
    return await payment_service.get_checkout_quote(
        session,
        current_user,
        product_id=product_id,
        quantity=quantity,
        display_currency=display_currency,
    )


@router.post(
    "/create-order",
    response_model=PaymentOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a backend-verified PayPal checkout order",
)
async def create_order(
    request: Request,
    payload: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    payment_service: PaymentService = Depends(get_payment_service),
) -> PaymentOrderResponse:
    return await payment_service.create_order(
        session,
        current_user,
        payload,
        ip_address=get_client_ip(request),
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentOrderResponse,
    summary="Retrieve payment order status (and optionally sync with PayPal)",
)
async def get_payment(
    payment_id: str,
    sync: bool = Query(default=True),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    payment_service: PaymentService = Depends(get_payment_service),
) -> PaymentOrderResponse:
    return await payment_service.get_payment_order(
        session,
        current_user,
        payment_id,
        sync_with_paypal=sync,
    )


@router.post(
    "/{payment_id}/capture",
    response_model=PaymentOrderResponse,
    summary="Capture funds for an order after verified PayPal buyer approval",
)
async def capture_payment(
    request: Request,
    payment_id: str,
    payload: CapturePaymentRequest | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    payment_service: PaymentService = Depends(get_payment_service),
) -> PaymentOrderResponse:
    confirm = payload.confirm_capture if payload else True
    return await payment_service.capture_payment(
        session,
        current_user,
        payment_id,
        confirm_capture=confirm,
        ip_address=get_client_ip(request),
    )


@router.post(
    "/{payment_id}/cancel",
    response_model=PaymentOrderResponse,
    summary="Cancel an uncaptured payment order",
)
async def cancel_payment(
    request: Request,
    payment_id: str,
    payload: CancelPaymentRequest | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    payment_service: PaymentService = Depends(get_payment_service),
) -> PaymentOrderResponse:
    reason = payload.reason if payload else None
    return await payment_service.cancel_payment(
        session,
        current_user,
        payment_id,
        reason=reason,
        ip_address=get_client_ip(request),
    )


@router.post(
    "/{payment_id}/refund",
    response_model=PaymentOrderResponse,
    summary="Refund a completed PayPal capture back to the buyer",
)
async def refund_payment(
    request: Request,
    payment_id: str,
    payload: RefundPaymentRequest | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    payment_service: PaymentService = Depends(get_payment_service),
) -> PaymentOrderResponse:
    reason = payload.reason if payload else None
    return await payment_service.refund_payment(
        session,
        current_user,
        payment_id,
        reason=reason,
        ip_address=get_client_ip(request),
    )

