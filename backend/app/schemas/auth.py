from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import validate_password_strength
from app.utils.currency import validate_currency_code


class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, examples=["Alex Morgan"])
    email: EmailStr = Field(..., examples=["alex@example.com"])
    password: str = Field(..., min_length=8, max_length=128, examples=["StrongPass123!"])

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if len(cleaned) < 2:
            raise ValueError("Name must contain at least 2 characters.")
        return cleaned

    @field_validator("password")
    @classmethod
    def check_password_strength(cls, value: str) -> str:
        errors = validate_password_strength(value)
        if errors:
            raise ValueError(" ".join(errors))
        return value


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["alex@example.com"])
    password: str = Field(..., min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=16)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=16)


class UserProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    max_single_transaction: Decimal | None = Field(default=None, gt=0)
    daily_limit: Decimal | None = Field(default=None, gt=0)
    monthly_limit: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    require_manual_approval: bool | None = Field(default=None)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        if len(cleaned) < 2:
            raise ValueError("Name must contain at least 2 characters.")
        return cleaned

    @field_validator("currency")
    @classmethod
    def check_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_currency_code(value)


class SpendingLimitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency: str
    max_single_transaction: Decimal
    daily_limit: Decimal
    monthly_limit: Decimal
    require_manual_approval: bool


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: EmailStr
    is_active: bool
    created_at: datetime
    updated_at: datetime
    spending_limit: SpendingLimitResponse | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class MessageResponse(BaseModel):
    message: str

