from __future__ import annotations

import asyncio
import sys
import time
import uuid

if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    if not isinstance(
        asyncio.get_event_loop_policy(), asyncio.WindowsSelectorEventLoopPolicy
    ):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.dependencies import get_current_user, get_shared_paypal_client
from app.api.routes import (
    agents,
    auth,
    commerce,
    payments,
    products,
    transactions,
    webhooks,
)
from app.core.config import get_settings
from app.core.database import (
    DatabaseNotConfiguredError,
    check_database_health,
    close_db,
    init_db,
)
from app.core.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
)
from app.core.observability import observability
from app.core.security import api_rate_limiter, auth_rate_limiter, get_client_ip
from app.llm.router import LLMRouter
from app.models.user import User

logger = get_logger(__name__)

API_DESCRIPTION = """
## PayPilot AI Backend API

Autonomous multi-agent commerce platform with strict server-side payment controls and PayPal Orders API v2 integration.

### Authentication
- Register via `POST /api/v1/auth/register` or authenticate via `POST /api/v1/auth/login`.
- Pass the returned JWT access token in `Authorization: Bearer <token>`.
- Rotate refresh tokens via `POST /api/v1/auth/refresh`; reuse of revoked refresh tokens revokes the entire session family.

### Multi-Agent AI Workflow
1. `POST /api/v1/commerce/request` (or `POST /api/v1/agents/run`) invokes:
   - **Lead Agent (NVIDIA Nemotron)**: parses intent, constraints, currency, and execution plan.
   - **Discovery Agent**: queries verified external product providers (Channel3 or explicit `TEST DATA` fixtures when enabled).
   - **Comparison Agent**: performs deterministic `Decimal` price/spec comparison (optionally enriched by Mistral).
   - **Decision Agent**: ranks options grounded strictly in retrieved product records.
   - **Security Agent**: validates spending limits, merchant metadata, and risk posture (advisory only; never authorizes payment).
2. Workflow pauses at `AWAITING_USER_APPROVAL`.
3. User explicitly approves via `POST /api/v1/commerce/workflows/{workflow_id}/approve` to authorize order preparation.

### PayPal Payment Workflow
1. Create order (`POST /api/v1/payments/create-order` or via workflow approval) using backend-calculated `Decimal` amounts and idempotency keys.
2. User completes checkout approval via PayPal's `approval_url`.
3. Capture payment (`POST /api/v1/payments/{payment_id}/capture`) only after PayPal confirms `APPROVED` status and amount integrity.
4. Asynchronous reconciliation via `POST /api/v1/webhooks/paypal` verified through PayPal's signature verification API.

### Error Codes
- `400 Bad Request`: Validation, currency, or workflow state error.
- `401 Unauthorized`: Missing, invalid, or expired JWT / invalid webhook signature.
- `403 Forbidden`: Resource ownership mismatch or spending limit violation.
- `404 Not Found`: Requested resource does not exist.
- `409 Conflict`: Duplicate registration, idempotency conflict, amount mismatch, or invalid payment state transition.
- `429 Too Many Requests`: Auth rate limit exceeded.
- `502 Bad Gateway`: Upstream PayPal API failure.
- `503 Service Unavailable`: Required integration or database is `NOT_CONFIGURED`.
"""

OPENAPI_TAGS = [
    {"name": "Health", "description": "Service and integration health probes."},
    {"name": "Authentication", "description": "User registration, JWT auth, refresh rotation, and profile limits."},
    {"name": "AI Agents", "description": "Direct multi-agent execution, status polling, activity logs, and cancellation."},
    {"name": "Autonomous Commerce", "description": "End-to-end shopping workflows and explicit human purchase approvals."},
    {"name": "Products", "description": "Verified product search, details, and deterministic comparisons."},
    {"name": "Payments (PayPal)", "description": "Server-side PayPal Orders v2 creation, status sync, capture, and cancellation."},
    {"name": "Transactions", "description": "User transaction history and exact Decimal financial summaries."},
    {"name": "Webhooks", "description": "Cryptographically verified PayPal webhook ingestion."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(debug=settings.debug, app_env=settings.app_env)

    if settings.uses_ephemeral_secrets:
        logger.warning(
            "ephemeral_secrets_active",
            app_env=settings.app_env,
            message="SECRET_KEY or JWT_SECRET_KEY not set; using ephemeral development secrets.",
        )

    init_db(settings)
    logger.info(
        "application_startup",
        app_name=settings.app_name,
        app_env=settings.app_env,
        database_configured=settings.is_database_configured,
        nvidia_configured=settings.is_nvidia_configured,
        mistral_configured=settings.is_mistral_configured,
        groq_configured=settings.is_groq_configured,
        paypal_configured=settings.is_paypal_configured,
        channel3_configured=settings.is_channel3_configured,
    )
    try:
        yield
    finally:
        auth_rate_limiter.reset()
        api_rate_limiter.reset()
        await close_db()
        logger.info("application_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    show_docs = settings.app_env != "production" or settings.expose_api_docs_in_prod

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs" if show_docs else None,
        redoc_url="/redoc" if show_docs else None,
        openapi_url="/openapi.json" if show_docs else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context_and_security_headers(request: Request, call_next):
        cfg = get_settings()
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        started = time.perf_counter()
        bind_request_context(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        def _attach_security_headers(resp: Any) -> Any:
            resp.headers["X-Request-ID"] = request_id
            resp.headers["X-Content-Type-Options"] = "nosniff"
            resp.headers["X-Frame-Options"] = "DENY"
            resp.headers["Referrer-Policy"] = "no-referrer"
            resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            if request.url.path.startswith("/api/"):
                resp.headers["Cache-Control"] = "no-store"
            if cfg.app_env == "production":
                resp.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )
            return resp

        try:
            # 1. Request body size limit check
            content_len_hdr = request.headers.get("content-length")
            if content_len_hdr:
                try:
                    if int(content_len_hdr) > cfg.max_request_body_bytes:
                        observability.record_http_request(413, (time.perf_counter() - started) * 1000.0)
                        return _attach_security_headers(
                            JSONResponse(
                                status_code=413,
                                content={
                                    "error": {
                                        "code": "PAYLOAD_TOO_LARGE",
                                        "message": "Request payload exceeds allowed size limit.",
                                    }
                                },
                            )
                        )
                except ValueError:
                    observability.record_http_request(400, (time.perf_counter() - started) * 1000.0)
                    return _attach_security_headers(
                        JSONResponse(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            content={
                                "error": {
                                    "code": "INVALID_CONTENT_LENGTH",
                                    "message": "Invalid Content-Length header.",
                                }
                            },
                        )
                    )

            if request.method in {"POST", "PUT", "PATCH"}:
                raw_body = await request.body()
                if len(raw_body) > cfg.max_request_body_bytes:
                    observability.record_http_request(413, (time.perf_counter() - started) * 1000.0)
                    return _attach_security_headers(
                        JSONResponse(
                            status_code=413,
                            content={
                                "error": {
                                    "code": "PAYLOAD_TOO_LARGE",
                                    "message": "Request payload exceeds allowed size limit.",
                                }
                            },
                        )
                    )

            # 2. General API rate limiting (excluding webhook ingestion & health probes)
            if (
                request.url.path.startswith("/api/")
                and not request.url.path.startswith(f"{cfg.api_v1_prefix}/webhooks")
                and not request.url.path.startswith(f"{cfg.api_v1_prefix}/health")
                and not request.url.path.startswith(f"{cfg.api_v1_prefix}/ready")
            ):
                client_ip = get_client_ip(request)
                try:
                    await api_rate_limiter.check(
                        f"api:{client_ip}",
                        max_requests=cfg.rate_limit_api_requests,
                        window_seconds=cfg.rate_limit_api_window_seconds,
                    )
                except HTTPException as rate_exc:
                    observability.record_http_request(429, (time.perf_counter() - started) * 1000.0)
                    resp = JSONResponse(
                        status_code=rate_exc.status_code,
                        headers=rate_exc.headers,
                        content={
                            "detail": rate_exc.detail,
                            "error": {
                                "code": "RATE_LIMIT_EXCEEDED",
                                "message": rate_exc.detail,
                            },
                        },
                    )
                    return _attach_security_headers(resp)

            # 3. Execute route within configured safety timeout
            try:
                response = await asyncio.wait_for(
                    call_next(request), timeout=cfg.request_timeout_seconds
                )
            except asyncio.TimeoutError:
                latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
                observability.record_http_request(504, latency_ms)
                logger.error("request_timeout", path=request.url.path, latency_ms=latency_ms)
                return _attach_security_headers(
                    JSONResponse(
                        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                        content={
                            "error": {
                                "code": "REQUEST_TIMEOUT",
                                "message": "Request processing timed out.",
                            }
                        },
                    )
                )

            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            observability.record_http_request(response.status_code, latency_ms)
            return _attach_security_headers(response)
        finally:
            clear_request_context()

    # Centralized Exception Handlers (never leak internal tracebacks)
    @app.exception_handler(DatabaseNotConfiguredError)
    async def database_not_configured_handler(
        request: Request, exc: DatabaseNotConfiguredError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": "DATABASE_NOT_CONFIGURED",
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = []
        for err in exc.errors():
            errors.append(
                {
                    "field": ".".join(str(loc) for loc in err.get("loc", [])),
                    "message": err.get("msg"),
                    "type": err.get("type"),
                }
            )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "details": errors,
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "detail": exc.detail,
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail,
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("unhandled_server_error", path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected internal error occurred.",
                }
            },
        )

    # Health & Readiness Monitoring Endpoints
    @app.get("/health", tags=["Health"], summary="Root liveness and service summary")
    async def root_health() -> dict[str, Any]:
        cfg = get_settings()
        return {
            "status": "HEALTHY",
            "service": cfg.app_name,
            "environment": cfg.app_env,
        }

    async def _compute_readiness() -> tuple[int, dict[str, Any]]:
        cfg = get_settings()
        db_status, db_detail = await check_database_health()
        ready = db_status == "HEALTHY"
        if cfg.app_env == "production":
            ready = (
                ready
                and cfg.is_nvidia_configured
                and cfg.is_paypal_configured
                and bool(cfg.paypal_webhook_id.strip())
            )
        payload = {
            "status": "READY" if ready else "NOT_READY",
            "service": cfg.app_name,
            "environment": cfg.app_env,
            "checks": {
                "database": {"status": db_status, "detail": db_detail},
                "ai_primary": "CONFIGURED" if cfg.is_nvidia_configured else "NOT_CONFIGURED",
                "paypal": "CONFIGURED" if cfg.is_paypal_configured else "NOT_CONFIGURED",
            },
        }
        return (status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE), payload

    @app.get("/ready", tags=["Health"], summary="Container/orchestrator readiness probe")
    async def root_readiness() -> JSONResponse:
        code, payload = await _compute_readiness()
        return JSONResponse(status_code=code, content=payload)

    @app.get(
        f"{settings.api_v1_prefix}/ready",
        tags=["Health"],
        summary="v1 service readiness probe",
    )
    async def api_v1_readiness() -> JSONResponse:
        code, payload = await _compute_readiness()
        return JSONResponse(status_code=code, content=payload)

    @app.get(
        f"{settings.api_v1_prefix}/metrics",
        tags=["Health"],
        summary="Authenticated application runtime telemetry and AI token/latency metrics",
    )
    async def runtime_metrics(_: User = Depends(get_current_user)) -> dict[str, Any]:
        return observability.snapshot()

    @app.get(
        f"{settings.api_v1_prefix}/health",
        tags=["Health"],
        summary="Aggregated v1 health report across database, AI, and PayPal integrations",
    )
    async def api_v1_health(
        verify: bool = Query(
            default=False,
            description="When true, executes live outbound connectivity checks against configured external APIs.",
        )
    ) -> dict[str, Any]:
        cfg = get_settings()
        db_status, db_detail = await check_database_health()
        ai_health = await LLMRouter(cfg).check_all_providers(verify_remote=verify)
        paypal_health = await get_shared_paypal_client().check_health(
            verify_remote=verify
        )
        return {
            "status": "DEGRADED" if db_status == "UNHEALTHY" else "HEALTHY",
            "service": cfg.app_name,
            "environment": cfg.app_env,
            "integrations": {
                "database": {"status": db_status, "detail": db_detail},
                "ai": ai_health,
                "paypal": paypal_health,
                "product_discovery": {
                    "provider": "channel3"
                    if cfg.is_channel3_configured
                    else ("test_fixtures" if cfg.enable_test_product_fixtures else "channel3"),
                    "status": (
                        "CONFIGURED"
                        if cfg.is_channel3_configured
                        else ("TEST_FIXTURES" if cfg.enable_test_product_fixtures else "NOT_CONFIGURED")
                    ),
                },
            },
        }

    @app.get(
        f"{settings.api_v1_prefix}/health/database",
        tags=["Health"],
        summary="Database connectivity status",
    )
    async def database_health() -> dict[str, str]:
        db_status, db_detail = await check_database_health()
        return {"status": db_status, "detail": db_detail}

    @app.get(
        f"{settings.api_v1_prefix}/health/ai",
        tags=["Health"],
        summary="AI LLM providers configuration and connectivity status",
    )
    async def ai_health(
        verify: bool = Query(default=True),
    ) -> dict[str, Any]:
        return await LLMRouter(get_settings()).check_all_providers(verify_remote=verify)

    @app.get(
        f"{settings.api_v1_prefix}/health/paypal",
        tags=["Health"],
        summary="PayPal REST API configuration and OAuth2 connectivity status",
    )
    async def paypal_health(
        verify: bool = Query(default=True),
    ) -> dict[str, Any]:
        return await get_shared_paypal_client().check_health(verify_remote=verify)

    # Mount API v1 routers
    v1_prefix = settings.api_v1_prefix
    app.include_router(auth.router, prefix=v1_prefix)
    app.include_router(agents.router, prefix=v1_prefix)
    app.include_router(commerce.router, prefix=v1_prefix)
    app.include_router(products.router, prefix=v1_prefix)
    app.include_router(payments.router, prefix=v1_prefix)
    app.include_router(transactions.router, prefix=v1_prefix)
    app.include_router(webhooks.router, prefix=v1_prefix)

    return app


app = create_app()

