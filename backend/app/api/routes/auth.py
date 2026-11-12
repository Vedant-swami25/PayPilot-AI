from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    enforce_auth_rate_limit,
    get_auth_service,
    get_current_user,
    oauth2_scheme,
)
from app.core.database import get_db
from app.core.security import get_client_ip
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserProfileUpdateRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new PayPilot AI user account",
)
async def register(
    request: Request,
    payload: UserRegisterRequest,
    _: None = Depends(enforce_auth_rate_limit),
    session: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await auth_service.register_user(
        session, payload, ip_address=get_client_ip(request)
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Authenticate user and issue JWT access + refresh tokens",
)
async def login(
    request: Request,
    payload: UserLoginRequest,
    _: None = Depends(enforce_auth_rate_limit),
    session: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await auth_service.login_user(
        session, payload, ip_address=get_client_ip(request)
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and issue a fresh token pair",
)
async def refresh_token(
    request: Request,
    payload: RefreshTokenRequest,
    _: None = Depends(enforce_auth_rate_limit),
    session: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return await auth_service.refresh_tokens(
        session, payload.refresh_token, ip_address=get_client_ip(request)
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke refresh token(s) and end authenticated session",
)
async def logout(
    request: Request,
    payload: LogoutRequest | None = None,
    _token: str | None = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await auth_service.logout_user(
        session,
        current_user,
        raw_refresh_token=payload.refresh_token if payload else None,
        ip_address=get_client_ip(request),
    )
    return MessageResponse(message="Logged out successfully.")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Retrieve the authenticated user's profile and spending limits",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update authenticated user's profile or spending guardrails",
)
async def update_me(
    request: Request,
    payload: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    return await auth_service.update_profile(
        session,
        current_user,
        payload,
        ip_address=get_client_ip(request),
    )

