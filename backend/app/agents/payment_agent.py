from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AgentExecutionError, AgentExecutionStatus, BaseAgent
from app.core.config import Settings, get_settings
from app.models.agent_activity import CommerceWorkflow
from app.models.user import User
from app.schemas.payment import CreateOrderRequest, PaymentOrderResponse
from app.services.payment_service import PaymentService


class PaymentAgent(BaseAgent):
    """Agent responsible for preparing and tracking backend-authorized PayPal payments."""

    agent_name = "PAYMENT_AGENT"

    def __init__(
        self,
        payment_service: PaymentService | None = None,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        super().__init__(timeout_seconds=cfg.agent_timeout_seconds)
        self.settings = cfg
        self.payment_service = payment_service or PaymentService(cfg)

    async def _run(self, *args: Any, **kwargs: Any) -> tuple[str, PaymentOrderResponse]:
        action: str = kwargs.get("action", "create_order")
        session: AsyncSession = kwargs["session"]
        user: User = kwargs["user"]
        ip_address: str | None = kwargs.get("ip_address")

        if action == "create_order":
            workflow: CommerceWorkflow = kwargs["workflow"]
            if workflow.status not in {"APPROVED", "ORDER_CREATED"} or workflow.approved_at is None:
                raise AgentExecutionError(
                    "PaymentAgent cannot create a PayPal order without explicit user approval.",
                    agent_name=self.agent_name,
                    status=AgentExecutionStatus.BLOCKED,
                )

            request = CreateOrderRequest(
                workflow_id=workflow.id,
                product_id=workflow.approved_product_id,
                quantity=int(kwargs.get("quantity", 1)),
                return_url=kwargs.get("return_url") or "http://localhost:5173/checkout/success",
                cancel_url=kwargs.get("cancel_url") or "http://localhost:5173/checkout/cancel",
                idempotency_key=kwargs.get("idempotency_key"),
            )
            try:
                order_resp = await self.payment_service.create_order(
                    session, user, request, ip_address=ip_address
                )
            except HTTPException as exc:
                mapped_status = (
                    AgentExecutionStatus.NOT_CONFIGURED
                    if exc.status_code == 503
                    else AgentExecutionStatus.FAILED
                )
                raise AgentExecutionError(
                    str(exc.detail),
                    agent_name=self.agent_name,
                    status=mapped_status,
                ) from exc

            summary = (
                f"Prepared PayPal order {order_resp.paypal_order_id} "
                f"for {order_resp.amount} {order_resp.currency} (status={order_resp.status})."
            )
            return summary, order_resp

        if action == "capture_order":
            payment_id: str = kwargs["payment_id"]
            try:
                order_resp = await self.payment_service.capture_payment(
                    session,
                    user,
                    payment_id,
                    confirm_capture=True,
                    ip_address=ip_address,
                )
            except HTTPException as exc:
                raise AgentExecutionError(
                    str(exc.detail),
                    agent_name=self.agent_name,
                    status=AgentExecutionStatus.FAILED,
                ) from exc

            summary = (
                f"Captured PayPal order {order_resp.paypal_order_id} "
                f"(status={order_resp.status})."
            )
            return summary, order_resp

        raise AgentExecutionError(
            f"Unsupported PaymentAgent action '{action}'.",
            agent_name=self.agent_name,
            status=AgentExecutionStatus.FAILED,
        )

