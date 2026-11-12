from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_payment_service
from app.core.database import get_db
from app.core.security import get_client_ip
from app.schemas.transaction import WebhookResponse
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/paypal",
    response_model=WebhookResponse,
    summary="Receive and cryptographically verify PayPal payment webhook events",
    description=(
        "Verifies PayPal webhook headers and signature against PayPal's "
        "/v1/notifications/verify-webhook-signature endpoint, deduplicates event IDs, "
        "and safely updates order/transaction state including out-of-order events."
    ),
)
async def paypal_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
    payment_service: PaymentService = Depends(get_payment_service),
) -> WebhookResponse:
    raw_body = await request.body()
    try:
        event_payload: dict[str, Any] = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook payload must be valid UTF-8 JSON.",
        ) from exc

    if not isinstance(event_payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook payload root must be a JSON object.",
        )

    return await payment_service.process_paypal_webhook(
        session,
        headers=request.headers,
        event_payload=event_payload,
        ip_address=get_client_ip(request),
    )

