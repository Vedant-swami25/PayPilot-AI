from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import HTTPException, Request, status

from app.core.config import Settings, get_settings

_password_hasher = PasswordHasher()


class TokenValidationError(Exception):
    """Raised when a JWT access or refresh token fails validation."""


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored Argon2 hash."""
    if not plain_password or not password_hash:
        return False
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """Return True if stored Argon2 hash parameters should be upgraded."""
    try:
        return _password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False


def validate_password_strength(password: str) -> list[str]:
    """Validate minimum password complexity rules and return any violations."""
    errors: list[str] = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if len(password) > 128:
        errors.append("Password must not exceed 128 characters.")
    if not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter.")
    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter.")
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit.")
    return errors


def hash_token(raw_token: str) -> str:
    """Return deterministic SHA-256 hex digest of a token for safe storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    user_id: str,
    email: str,
    settings: Settings | None = None,
    expires_delta: timedelta | None = None,
) -> tuple[str, str, datetime]:
    """Create a signed JWT access token. Returns (token, jti, expires_at)."""
    cfg = settings or get_settings()
    now = utc_now()
    delta = expires_delta or timedelta(minutes=cfg.jwt_access_token_expire_minutes)
    expires_at = now + delta
    jti = str(uuid.uuid4())

    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": cfg.jwt_issuer,
        "aud": cfg.jwt_audience,
    }
    token = jwt.encode(payload, cfg.get_jwt_secret_key(), algorithm=cfg.jwt_algorithm)
    return token, jti, expires_at


def create_refresh_token(
    user_id: str,
    family_id: str | None = None,
    settings: Settings | None = None,
    expires_delta: timedelta | None = None,
) -> tuple[str, str, str, datetime]:
    """Create a signed JWT refresh token. Returns (token, jti, family_id, expires_at)."""
    cfg = settings or get_settings()
    now = utc_now()
    delta = expires_delta or timedelta(days=cfg.jwt_refresh_token_expire_days)
    expires_at = now + delta
    jti = str(uuid.uuid4())
    token_family = family_id or str(uuid.uuid4())

    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": jti,
        "family_id": token_family,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": cfg.jwt_issuer,
        "aud": cfg.jwt_audience,
    }
    token = jwt.encode(payload, cfg.get_jwt_secret_key(), algorithm=cfg.jwt_algorithm)
    return token, jti, token_family, expires_at


def decode_jwt_token(
    token: str,
    expected_type: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Verify JWT signature, claims, expiration, and token type."""
    cfg = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            cfg.get_jwt_secret_key(),
            algorithms=[cfg.jwt_algorithm],
            audience=cfg.jwt_audience,
            issuer=cfg.jwt_issuer,
            options={"require": ["sub", "exp", "iat", "jti", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenValidationError("Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenValidationError("Invalid authentication token.") from exc

    if payload.get("type") != expected_type:
        raise TokenValidationError(
            f"Invalid token type: expected '{expected_type}'."
        )
    return payload


def generate_idempotency_key(prefix: str = "paypilot") -> str:
    """Generate a unique idempotency key for external payment API calls."""
    return f"{prefix}-{uuid.uuid4()}"


def constant_time_compare(a: str, b: str) -> bool:
    """Perform timing-safe string comparison."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


class SlidingWindowRateLimiter:
    """In-memory async sliding-window rate limiter keyed by client IP and route."""

    def __init__(self, max_keys: int = 10000) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._max_keys = max_keys
        self._checks_since_prune = 0

    def _prune_stale(self, now: float, window_seconds: int) -> None:
        cutoff = now - window_seconds
        stale_keys = [
            key
            for key, bucket in self._hits.items()
            if not bucket or bucket[-1] <= cutoff
        ]
        for key in stale_keys:
            del self._hits[key]

    async def check(self, key: str, max_requests: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        async with self._lock:
            self._checks_since_prune += 1
            if self._checks_since_prune >= 500 or len(self._hits) > self._max_keys:
                self._prune_stale(now, window_seconds)
                self._checks_since_prune = 0

            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= max_requests:
                retry_after = max(1, int(bucket[0] + window_seconds - now) + 1)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.append(now)

    def reset(self) -> None:
        self._hits.clear()
        self._checks_since_prune = 0


auth_rate_limiter = SlidingWindowRateLimiter()
api_rate_limiter = SlidingWindowRateLimiter()


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request headers or socket peer."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"

