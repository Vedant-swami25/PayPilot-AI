from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents import AgentExecutionStatus
from app.agents.comparison_agent import ComparisonAgent
from app.agents.decision_agent import DecisionAgent
from app.agents.discovery_agent import DiscoveryAgent
from app.agents.lead_agent import LeadAgent
from app.agents.monitoring_agent import MonitoringAgent
from app.agents.payment_agent import PaymentAgent
from app.agents.security_agent import SecurityAgent
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.security import utc_now
from app.llm.router import LLMRouter
from app.models.agent_activity import CommerceWorkflow
from app.models.product import Product
from app.models.user import User
from app.schemas.commerce import WorkflowApprovalRequest
from app.services.audit_service import AuditService
from app.services.payment_service import PaymentService
from app.services.product_service import ProductService
from app.services.transaction_service import TransactionService
from app.utils.currency import calculate_order_total

logger = get_logger(__name__)


class CommerceOrchestrator:
    """Central multi-agent orchestration engine managing workflow state and resumable checkout."""

    def __init__(
        self,
        settings: Settings | None = None,
        llm_router: LLMRouter | None = None,
        product_service: ProductService | None = None,
        payment_service: PaymentService | None = None,
        audit_service: AuditService | None = None,
        transaction_service: TransactionService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.router = llm_router or LLMRouter(self.settings)
        self.audit = audit_service or AuditService()
        self.product_service = product_service or ProductService(self.settings)
        self.payment_service = payment_service or PaymentService(
            self.settings, audit_service=self.audit
        )
        self.transaction_service = transaction_service or TransactionService()

        self.lead_agent = LeadAgent(self.router, self.settings)
        self.discovery_agent = DiscoveryAgent(
            self.product_service, self.router, self.settings
        )
        self.comparison_agent = ComparisonAgent(
            self.product_service, self.router, self.settings
        )
        self.decision_agent = DecisionAgent(self.router, self.settings)
        self.security_agent = SecurityAgent(self.router, self.settings)
        self.payment_agent = PaymentAgent(self.payment_service, self.settings)
        self.monitoring_agent = MonitoringAgent(
            self.audit, self.transaction_service, self.settings
        )

    async def _load_workflow(
        self, session: AsyncSession, workflow_id: str, user_id: str
    ) -> CommerceWorkflow:
        result = await session.execute(
            select(CommerceWorkflow)
            .options(selectinload(CommerceWorkflow.activities))
            .where(CommerceWorkflow.id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        if workflow is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found.",
            )
        if workflow.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this workflow.",
            )
        return workflow

    async def run_workflow(
        self,
        session: AsyncSession,
        *,
        user: User,
        request_text: str,
        budget: Decimal | None = None,
        currency: str | None = None,
        quantity: int = 1,
        idempotency_key: str | None = None,
        ip_address: str | None = None,
    ) -> CommerceWorkflow:
        # Prevent duplicate execution on idempotency_key
        if idempotency_key:
            existing_res = await session.execute(
                select(CommerceWorkflow)
                .options(selectinload(CommerceWorkflow.activities))
                .where(
                    CommerceWorkflow.user_id == user.id,
                    CommerceWorkflow.idempotency_key == idempotency_key,
                )
            )
            existing = existing_res.scalar_one_or_none()
            if existing is not None:
                return existing

        workflow = CommerceWorkflow(
            user_id=user.id,
            request_text=request_text,
            idempotency_key=idempotency_key,
            status="RUNNING",
            current_step="LEAD_AGENT",
        )
        session.add(workflow)
        await session.flush()

        # 1. LEAD AGENT - Request Understanding & Execution Planning (NVIDIA Nemotron)
        lead_res = await self.lead_agent.execute(
            "Parse shopping intent and create execution plan",
            mode="plan",
            request_text=request_text,
            explicit_budget=budget,
            explicit_currency=currency,
        )
        await self.monitoring_agent.record_step(
            session, user_id=user.id, workflow_id=workflow.id, result=lead_res
        )
        if lead_res.status != AgentExecutionStatus.SUCCESS or lead_res.data is None:
            workflow.status = (
                "NOT_CONFIGURED"
                if lead_res.status == AgentExecutionStatus.NOT_CONFIGURED
                else "FAILED"
            )
            workflow.error_message = lead_res.error or lead_res.summary
            await self.monitoring_agent.execute(
                "Record failed workflow telemetry",
                session=session,
                user_id=user.id,
                workflow_id=workflow.id,
                workflow_status=workflow.status,
                ip_address=ip_address,
            )
            await session.commit()
            return await self._load_workflow(session, workflow.id, user.id)

        plan = lead_res.data
        workflow.parsed_intent = plan.model_dump(mode="json")

        if plan.needs_clarification and not plan.search_query:
            workflow.status = "NEEDS_CLARIFICATION"
            workflow.current_step = "USER_CLARIFICATION"
            await session.commit()
            return await self._load_workflow(session, workflow.id, user.id)

        # 2. DISCOVERY AGENT - Verified External Product Search
        workflow.current_step = "DISCOVERY_AGENT"
        disc_res = await self.discovery_agent.execute(
            f"Search verified product provider for '{plan.search_query}'",
            session=session,
            search_query=plan.search_query,
            budget=plan.budget,
            currency=plan.currency,
            specifications=plan.specifications,
        )
        await self.monitoring_agent.record_step(
            session, user_id=user.id, workflow_id=workflow.id, result=disc_res
        )
        if disc_res.status != AgentExecutionStatus.SUCCESS or disc_res.data is None:
            workflow.status = (
                "NOT_CONFIGURED"
                if disc_res.status == AgentExecutionStatus.NOT_CONFIGURED
                else "FAILED"
            )
            workflow.error_message = disc_res.error or disc_res.summary
            await self.monitoring_agent.execute(
                "Record discovery failure telemetry",
                session=session,
                user_id=user.id,
                workflow_id=workflow.id,
                workflow_status=workflow.status,
                ip_address=ip_address,
            )
            await session.commit()
            return await self._load_workflow(session, workflow.id, user.id)

        discovery_out = disc_res.data
        workflow.discovered_products = [
            p.model_dump(mode="json") for p in discovery_out.products
        ]

        if not discovery_out.products:
            workflow.status = "NO_PRODUCTS_FOUND"
            workflow.current_step = "COMPLETED"
            workflow.error_message = discovery_out.limitation
            await self.monitoring_agent.execute(
                "Record empty discovery telemetry",
                session=session,
                user_id=user.id,
                workflow_id=workflow.id,
                workflow_status=workflow.status,
                ip_address=ip_address,
            )
            await session.commit()
            return await self._load_workflow(session, workflow.id, user.id)

        product_ids = [p.id for p in discovery_out.products]
        prod_rows_res = await session.execute(
            select(Product).where(Product.id.in_(product_ids))
        )
        prod_map = {p.id: p for p in prod_rows_res.scalars().all()}
        ordered_products = [prod_map[pid] for pid in product_ids if pid in prod_map]

        # 3. COMPARISON AGENT - Deterministic Price & Spec Evaluation
        workflow.current_step = "COMPARISON_AGENT"
        comp_res = await self.comparison_agent.execute(
            f"Compare {len(ordered_products)} candidate products",
            products=ordered_products,
            budget=plan.budget,
            currency=plan.currency,
            requirements=plan.specifications,
        )
        await self.monitoring_agent.record_step(
            session, user_id=user.id, workflow_id=workflow.id, result=comp_res
        )
        if comp_res.status != AgentExecutionStatus.SUCCESS or comp_res.data is None:
            workflow.status = "FAILED"
            workflow.error_message = comp_res.error or comp_res.summary
            await session.commit()
            return await self._load_workflow(session, workflow.id, user.id)

        comparison = comp_res.data
        workflow.comparison_result = comparison.model_dump(mode="json")

        # 4. DECISION AGENT - Grounded Ranking & Final Recommendation
        workflow.current_step = "DECISION_AGENT"
        dec_res = await self.decision_agent.execute(
            "Rank candidates and produce grounded recommendation",
            comparison=comparison,
            request_text=request_text,
        )
        await self.monitoring_agent.record_step(
            session, user_id=user.id, workflow_id=workflow.id, result=dec_res
        )
        if dec_res.status != AgentExecutionStatus.SUCCESS or dec_res.data is None:
            workflow.status = (
                "NOT_CONFIGURED"
                if dec_res.status == AgentExecutionStatus.NOT_CONFIGURED
                else "FAILED"
            )
            workflow.error_message = dec_res.error or dec_res.summary
            await session.commit()
            return await self._load_workflow(session, workflow.id, user.id)

        recommendation = dec_res.data
        workflow.recommendation = recommendation.model_dump(mode="json")

        # 5. SECURITY AGENT - Spending Limits, Merchant & Fraud Assessment
        workflow.current_step = "SECURITY_AGENT"
        rec_product = prod_map[recommendation.recommended_product_id]
        sec_res = await self.security_agent.execute(
            "Validate spending limits, merchant integrity, and risk",
            session=session,
            user=user,
            product=rec_product,
            quantity=quantity,
            budget=plan.budget,
            budget_currency=plan.currency,
        )
        await self.monitoring_agent.record_step(
            session, user_id=user.id, workflow_id=workflow.id, result=sec_res
        )
        if sec_res.status != AgentExecutionStatus.SUCCESS or sec_res.data is None:
            workflow.status = "FAILED"
            workflow.error_message = sec_res.error or sec_res.summary
            await session.commit()
            return await self._load_workflow(session, workflow.id, user.id)

        security_out = sec_res.data
        workflow.security_assessment = security_out.model_dump(mode="json")

        # 6. LEAD AGENT FINAL SYNTHESIS
        workflow.current_step = "LEAD_SYNTHESIS"
        synth_res = await self.lead_agent.execute(
            "Synthesize recommendation and safety validation for user approval",
            mode="synthesize",
            request_text=request_text,
            discovery_summary={
                "provider": discovery_out.provider,
                "is_test_data": discovery_out.is_test_data,
                "count": len(discovery_out.products),
            },
            comparison_summary={"summary": comparison.summary},
            recommendation=workflow.recommendation,
            security_assessment=workflow.security_assessment,
        )
        await self.monitoring_agent.record_step(
            session, user_id=user.id, workflow_id=workflow.id, result=synth_res
        )

        if security_out.block_execution:
            workflow.status = "BLOCKED_BY_SECURITY"
            workflow.current_step = "SECURITY_VALIDATION"
            workflow.error_message = "; ".join(security_out.policy_violations)
        else:
            workflow.status = "AWAITING_USER_APPROVAL"
            workflow.current_step = "USER_APPROVAL"

        # 7. MONITORING SNAPSHOT
        mon_res = await self.monitoring_agent.execute(
            "Record pre-approval workflow telemetry",
            session=session,
            user_id=user.id,
            workflow_id=workflow.id,
            workflow_status=workflow.status,
            ip_address=ip_address,
        )
        await self.monitoring_agent.record_step(
            session, user_id=user.id, workflow_id=workflow.id, result=mon_res
        )

        await session.commit()
        return await self._load_workflow(session, workflow.id, user.id)

    async def approve_workflow(
        self,
        session: AsyncSession,
        *,
        user: User,
        workflow_id: str,
        payload: WorkflowApprovalRequest,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        workflow = await self._load_workflow(session, workflow_id, user.id)

        if workflow.status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cancelled workflows cannot be approved.",
            )
        if workflow.status == "BLOCKED_BY_SECURITY":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workflow was blocked by security policy violations.",
            )

        # Resumable handling: if already approved and an order exists, return state cleanly
        if workflow.status in {"ORDER_CREATED", "COMPLETED"} and workflow.order_id:
            order_resp = await self.payment_service.get_payment_order(
                session, user, workflow.order_id, sync_with_paypal=True
            )
            return {
                "workflow": await self._load_workflow(session, workflow.id, user.id),
                "payment_order": order_resp,
            }

        if workflow.status not in {"AWAITING_USER_APPROVAL", "APPROVED"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Workflow in status '{workflow.status}' cannot be approved.",
            )

        if not payload.confirm_purchase:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Explicit purchase confirmation (confirm_purchase=true) is required.",
            )

        # Verify selected product came from this workflow's discovered products
        discovered_ids = {
            item.get("id")
            for item in (workflow.discovered_products or [])
            if isinstance(item, dict) and item.get("id")
        }
        rec_id = (workflow.recommendation or {}).get("recommended_product_id")
        chosen_product_id = payload.product_id or workflow.approved_product_id or rec_id

        if not chosen_product_id or chosen_product_id not in discovered_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected product does not belong to this workflow's discovered products.",
            )

        prod_res = await session.execute(
            select(Product).where(Product.id == chosen_product_id)
        )
        product = prod_res.scalar_one_or_none()
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected product no longer exists.",
            )

        # Re-run deterministic security verification for chosen product & quantity
        budget_val = (workflow.parsed_intent or {}).get("budget")
        budget_dec = Decimal(str(budget_val)) if budget_val is not None else None
        budget_currency = (workflow.parsed_intent or {}).get("currency") or product.currency
        sec_res = await self.security_agent.execute(
            "Re-verify security & spending limits on user approval",
            session=session,
            user=user,
            product=product,
            quantity=payload.quantity,
            budget=budget_dec,
            budget_currency=budget_currency,
        )
        await self.monitoring_agent.record_step(
            session, user_id=user.id, workflow_id=workflow.id, result=sec_res
        )
        if sec_res.status != AgentExecutionStatus.SUCCESS or sec_res.data is None:
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Security verification failed during approval.",
            )
        if sec_res.data.block_execution:
            workflow.status = "BLOCKED_BY_SECURITY"
            workflow.security_assessment = sec_res.data.model_dump(mode="json")
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="; ".join(sec_res.data.policy_violations),
            )

        quote = await self.payment_service.resolve_checkout_quote(
            product,
            quantity=payload.quantity,
            display_currency=budget_currency,
        )
        if not quote.can_checkout:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=quote.blocking_reason
                or "Merchant price and PayPal payment currency cannot be reconciled safely.",
            )

        approved_amount = quote.payable_amount
        workflow.approved_product_id = product.id
        workflow.approved_amount = approved_amount
        workflow.approved_currency = quote.payable_currency
        workflow.approved_at = workflow.approved_at or utc_now()
        workflow.status = "APPROVED"
        workflow.current_step = "PAYMENT_AGENT"

        await self.audit.record_audit_log(
            session,
            user_id=user.id,
            action="WORKFLOW_USER_APPROVED",
            resource_type="commerce_workflow",
            resource_id=workflow.id,
            status="SUCCESS",
            ip_address=ip_address,
            details={
                "product_id": product.id,
                "quantity": payload.quantity,
                "approved_amount": str(approved_amount),
                "currency": quote.payable_currency,
                "original_amount": str(quote.original_amount),
                "original_currency": quote.original_currency,
                "display_amount": str(quote.display_amount),
                "display_currency": quote.display_currency,
            },
        )
        await session.flush()

        payment_order = None
        if payload.create_paypal_order:
            pay_res = await self.payment_agent.execute(
                "Create PayPal checkout order for approved workflow",
                action="create_order",
                session=session,
                user=user,
                workflow=workflow,
                quantity=payload.quantity,
                return_url=payload.return_url,
                cancel_url=payload.cancel_url,
                idempotency_key=f"wf-{workflow.id}-order",
                ip_address=ip_address,
            )
            await self.monitoring_agent.record_step(
                session, user_id=user.id, workflow_id=workflow.id, result=pay_res
            )
            if pay_res.status != AgentExecutionStatus.SUCCESS:
                await session.commit()
                code = (
                    status.HTTP_503_SERVICE_UNAVAILABLE
                    if pay_res.status == AgentExecutionStatus.NOT_CONFIGURED
                    else status.HTTP_502_BAD_GATEWAY
                )
                raise HTTPException(
                    status_code=code,
                    detail=pay_res.error or pay_res.summary,
                )
            payment_order = pay_res.data

        mon_res = await self.monitoring_agent.execute(
            "Record approval and payment preparation telemetry",
            session=session,
            user_id=user.id,
            workflow_id=workflow.id,
            workflow_status=workflow.status,
            ip_address=ip_address,
        )
        await self.monitoring_agent.record_step(
            session, user_id=user.id, workflow_id=workflow.id, result=mon_res
        )
        await session.commit()

        return {
            "workflow": await self._load_workflow(session, workflow.id, user.id),
            "payment_order": payment_order,
        }

    async def cancel_workflow(
        self,
        session: AsyncSession,
        *,
        user: User,
        workflow_id: str,
        ip_address: str | None = None,
    ) -> CommerceWorkflow:
        workflow = await self._load_workflow(session, workflow_id, user.id)
        if workflow.status in {"COMPLETED", "CANCELLED"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Workflow in status '{workflow.status}' cannot be cancelled.",
            )

        workflow.status = "CANCELLED"
        workflow.current_step = "CANCELLED"
        await self.audit.record_audit_log(
            session,
            user_id=user.id,
            action="WORKFLOW_CANCELLED",
            resource_type="commerce_workflow",
            resource_id=workflow.id,
            status="SUCCESS",
            ip_address=ip_address,
        )
        await session.commit()
        return await self._load_workflow(session, workflow.id, user.id)

