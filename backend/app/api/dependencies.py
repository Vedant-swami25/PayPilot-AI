from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import (
    TokenValidationError,
    auth_rate_limiter,
    decode_jwt_token,
    get_client_ip,
)
from app.integrations.paypal.client import PayPalClient
from app.llm.router import LLMRouter
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.commerce_service import CommerceService
from app.services.payment_service import PaymentService
from app.services.product_service import ProductService
from app.services.transaction_service import TransactionService

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


@lru_cache(maxsize=1)
def get_shared_paypal_client() -> PayPalClient:
    """Shared PayPalClient instance so OAuth2 token caching persists across requests."""
    return PayPalClient(get_settings())


def reset_shared_clients() -> None:
    """Clear cached integration clients (used in tests)."""
    get_shared_paypal_client.cache_clear()


def get_audit_service() -> AuditService:
    return AuditService()


def get_auth_service(
    settings: Settings = Depends(get_settings),
    audit: AuditService = Depends(get_audit_service),
) -> AuthService:
    return AuthService(settings=settings, audit_service=audit)


def get_product_service(
    settings: Settings = Depends(get_settings),
) -> ProductService:
    return ProductService(settings=settings)


def get_transaction_service() -> TransactionService:
    return TransactionService()


def get_payment_service(
    settings: Settings = Depends(get_settings),
    audit: AuditService = Depends(get_audit_service),
) -> PaymentService:
    return PaymentService(
        settings=settings,
        paypal_client=get_shared_paypal_client(),
        audit_service=audit,
    )


def get_commerce_service(
    settings: Settings = Depends(get_settings),
    audit: AuditService = Depends(get_audit_service),
) -> CommerceService:
    from app.agents.orchestrator import CommerceOrchestrator

    orchestrator = CommerceOrchestrator(
        settings=settings,
        llm_router=LLMRouter(settings),
        product_service=ProductService(settings=settings),
        payment_service=PaymentService(
            settings=settings,
            paypal_client=get_shared_paypal_client(),
            audit_service=audit,
        ),
        audit_service=audit,
        transaction_service=TransactionService(),
    )
    return CommerceService(
        settings=settings,
        orchestrator=orchestrator,
        audit_service=audit,
    )


async def enforce_auth_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    """Rate-limit sensitive authentication endpoints per client IP and route."""
    ip = get_client_ip(request)
    key = f"auth:{request.url.path}:{ip}"
    await auth_rate_limiter.check(
        key,
        max_requests=settings.rate_limit_auth_requests,
        window_seconds=settings.rate_limit_auth_window_seconds,
    )


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """Authenticate Bearer JWT access token and return active User ORM model."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    try:
        payload = decode_jwt_token(
            token,
            expected_type="access",
            settings=settings,
        )
    except TokenValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception

    user = await auth_service.get_user_by_id(session, str(user_id))
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )
    return user

