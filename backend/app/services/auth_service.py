from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.security import (
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    utc_now,
    verify_password,
)
from app.models.user import RefreshToken, SpendingLimit, User
from app.schemas.auth import (
    AuthResponse,
    TokenResponse,
    UserLoginRequest,
    UserProfileUpdateRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.audit_service import AuditService
from app.utils.currency import quantize_amount, to_decimal
from app.utils.helpers import ensure_utc
from app.utils.validators import normalize_email


class AuthService:
    """Authentication, token rotation, and user profile management service."""

    def __init__(
        self,
        settings: Settings | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.audit = audit_service or AuditService()

    async def _issue_token_pair(
        self,
        session: AsyncSession,
        user: User,
        family_id: str | None = None,
    ) -> TokenResponse:
        access_token, _, _ = create_access_token(
            user_id=user.id,
            email=user.email,
            settings=self.settings,
        )
        refresh_token, jti, token_family, expires_at = create_refresh_token(
            user_id=user.id,
            family_id=family_id,
            settings=self.settings,
        )

        token_record = RefreshToken(
            user_id=user.id,
            jti=jti,
            family_id=token_family,
            token_hash=hash_token(refresh_token),
            expires_at=expires_at,
        )
        session.add(token_record)
        await session.flush()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=self.settings.jwt_access_token_expire_minutes * 60,
        )

    async def register_user(
        self,
        session: AsyncSession,
        payload: UserRegisterRequest,
        *,
        ip_address: str | None = None,
    ) -> AuthResponse:
        normalized_email = normalize_email(payload.email)
        existing = await session.execute(
            select(User).where(User.email == normalized_email)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        user = User(
            name=payload.name,
            email=normalized_email,
            password_hash=hash_password(payload.password),
            is_active=True,
        )
        session.add(user)
        await session.flush()

        default_limit = SpendingLimit(
            user_id=user.id,
            currency=self.settings.default_currency,
            max_single_transaction=to_decimal(self.settings.default_single_tx_limit),
            daily_limit=to_decimal(self.settings.default_daily_tx_limit),
            monthly_limit=Decimal("5000.00"),
            require_manual_approval=True,
        )
        session.add(default_limit)
        await session.flush()

        tokens = await self._issue_token_pair(session, user)
        await self.audit.record_audit_log(
            session,
            user_id=user.id,
            action="USER_REGISTERED",
            resource_type="user",
            resource_id=user.id,
            status="SUCCESS",
            ip_address=ip_address,
        )
        await session.commit()

        loaded_user = await self.get_user_by_id(session, user.id)
        return AuthResponse(
            user=UserResponse.model_validate(loaded_user),
            tokens=tokens,
        )

    async def login_user(
        self,
        session: AsyncSession,
        payload: UserLoginRequest,
        *,
        ip_address: str | None = None,
    ) -> AuthResponse:
        normalized_email = normalize_email(payload.email)
        result = await session.execute(
            select(User)
            .options(selectinload(User.spending_limit))
            .where(User.email == normalized_email)
        )
        user = result.scalar_one_or_none()

        if user is None or not verify_password(payload.password, user.password_hash):
            await self.audit.record_audit_log(
                session,
                user_id=user.id if user else None,
                action="USER_LOGIN_FAILED",
                resource_type="user",
                resource_id=user.id if user else None,
                status="FAILURE",
                ip_address=ip_address,
                details={"reason": "invalid_credentials"},
            )
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive.",
            )

        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(payload.password)

        tokens = await self._issue_token_pair(session, user)
        await self.audit.record_audit_log(
            session,
            user_id=user.id,
            action="USER_LOGIN_SUCCESS",
            resource_type="user",
            resource_id=user.id,
            status="SUCCESS",
            ip_address=ip_address,
        )
        await session.commit()

        return AuthResponse(
            user=UserResponse.model_validate(user),
            tokens=tokens,
        )

    async def refresh_tokens(
        self,
        session: AsyncSession,
        raw_refresh_token: str,
        *,
        ip_address: str | None = None,
    ) -> TokenResponse:
        try:
            payload = decode_jwt_token(
                raw_refresh_token,
                expected_type="refresh",
                settings=self.settings,
            )
        except TokenValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc

        token_digest = hash_token(raw_refresh_token)
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_digest)
        )
        token_record = result.scalar_one_or_none()

        if token_record is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is unrecognized.",
            )

        # Replay detection: revoke the entire token family if a rotated/revoked token is reused.
        if token_record.is_revoked:
            now = utc_now()
            await session.execute(
                update(RefreshToken)
                .where(RefreshToken.family_id == token_record.family_id)
                .values(is_revoked=True, revoked_at=now)
            )
            await self.audit.record_audit_log(
                session,
                user_id=token_record.user_id,
                action="REFRESH_TOKEN_REUSE_DETECTED",
                resource_type="refresh_token",
                resource_id=token_record.family_id,
                status="BLOCKED",
                ip_address=ip_address,
            )
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token reuse detected. Session family has been revoked.",
            )

        expires_at = ensure_utc(token_record.expires_at)
        if expires_at is None or expires_at <= utc_now():
            token_record.is_revoked = True
            token_record.revoked_at = utc_now()
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired.",
            )

        user = await self.get_user_by_id(session, payload["sub"])
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive or missing.",
            )

        # Rotate: revoke current refresh token and issue a fresh pair in same family
        token_record.is_revoked = True
        token_record.revoked_at = utc_now()
        new_tokens = await self._issue_token_pair(
            session, user, family_id=token_record.family_id
        )

        await self.audit.record_audit_log(
            session,
            user_id=user.id,
            action="TOKEN_REFRESHED",
            resource_type="refresh_token",
            resource_id=token_record.family_id,
            status="SUCCESS",
            ip_address=ip_address,
        )
        await session.commit()
        return new_tokens

    async def logout_user(
        self,
        session: AsyncSession,
        user: User,
        raw_refresh_token: str | None = None,
        *,
        ip_address: str | None = None,
    ) -> None:
        now = utc_now()
        if raw_refresh_token:
            token_digest = hash_token(raw_refresh_token)
            await session.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.user_id == user.id,
                    RefreshToken.token_hash == token_digest,
                )
                .values(is_revoked=True, revoked_at=now)
            )
        else:
            await session.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.user_id == user.id,
                    RefreshToken.is_revoked.is_(False),
                )
                .values(is_revoked=True, revoked_at=now)
            )

        await self.audit.record_audit_log(
            session,
            user_id=user.id,
            action="USER_LOGOUT",
            resource_type="user",
            resource_id=user.id,
            status="SUCCESS",
            ip_address=ip_address,
        )
        await session.commit()

    async def get_user_by_id(
        self, session: AsyncSession, user_id: str
    ) -> User | None:
        result = await session.execute(
            select(User)
            .options(selectinload(User.spending_limit))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_profile(
        self,
        session: AsyncSession,
        user: User,
        payload: UserProfileUpdateRequest,
        *,
        ip_address: str | None = None,
    ) -> UserResponse:
        if payload.name is not None:
            user.name = payload.name

        limit = user.spending_limit
        if limit is None:
            limit = SpendingLimit(
                user_id=user.id,
                currency=self.settings.default_currency,
                max_single_transaction=to_decimal(self.settings.default_single_tx_limit),
                daily_limit=to_decimal(self.settings.default_daily_tx_limit),
                monthly_limit=Decimal("5000.00"),
                require_manual_approval=True,
            )
            session.add(limit)
            user.spending_limit = limit

        currency = payload.currency or limit.currency
        new_single = (
            quantize_amount(payload.max_single_transaction, currency)
            if payload.max_single_transaction is not None
            else limit.max_single_transaction
        )
        new_daily = (
            quantize_amount(payload.daily_limit, currency)
            if payload.daily_limit is not None
            else limit.daily_limit
        )
        new_monthly = (
            quantize_amount(payload.monthly_limit, currency)
            if payload.monthly_limit is not None
            else limit.monthly_limit
        )

        if new_single > new_daily:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="max_single_transaction cannot exceed daily_limit.",
            )
        if new_daily > new_monthly:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="daily_limit cannot exceed monthly_limit.",
            )

        limit.currency = currency
        limit.max_single_transaction = new_single
        limit.daily_limit = new_daily
        limit.monthly_limit = new_monthly
        if payload.require_manual_approval is not None:
            limit.require_manual_approval = payload.require_manual_approval

        await self.audit.record_audit_log(
            session,
            user_id=user.id,
            action="USER_PROFILE_UPDATED",
            resource_type="user",
            resource_id=user.id,
            status="SUCCESS",
            ip_address=ip_address,
        )
        await session.commit()
        refreshed = await self.get_user_by_id(session, user.id)
        return UserResponse.model_validate(refreshed)

