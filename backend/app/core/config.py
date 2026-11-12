from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Annotated, Any
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class ConfigurationError(ValueError):
    """Raised when required application configuration is invalid or missing."""


class Settings(BaseSettings):
    """Centralized, environment-validated application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="PayPilot AI", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    api_v1_prefix: str = "/api/v1"

    # Security & JWT
    secret_key: SecretStr = Field(default=SecretStr(""), alias="SECRET_KEY")
    jwt_secret_key: SecretStr = Field(default=SecretStr(""), alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "paypilot-ai"
    jwt_audience: str = "paypilot-ai-clients"
    jwt_access_token_expire_minutes: int = Field(
        default=30, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES", ge=1, le=1440
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS", ge=1, le=90
    )

    # Database
    database_url: str = Field(default="", alias="DATABASE_URL")

    # AI Providers
    nvidia_api_key: SecretStr = Field(default=SecretStr(""), alias="NVIDIA_API_KEY")
    nvidia_model: str = Field(default="", alias="NVIDIA_MODEL")
    nvidia_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1", alias="NVIDIA_BASE_URL"
    )

    mistral_api_key: SecretStr = Field(default=SecretStr(""), alias="MISTRAL_API_KEY")
    mistral_model: str = Field(default="", alias="MISTRAL_MODEL")
    mistral_base_url: str = Field(
        default="https://api.mistral.ai/v1", alias="MISTRAL_BASE_URL"
    )

    groq_api_key: SecretStr = Field(default=SecretStr(""), alias="GROQ_API_KEY")
    groq_model: str = Field(default="", alias="GROQ_MODEL")
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL"
    )

    llm_timeout_seconds: float = Field(default=30.0, alias="LLM_TIMEOUT_SECONDS", ge=1.0, le=300.0)
    agent_timeout_seconds: float = Field(
        default=90.0, alias="AGENT_TIMEOUT_SECONDS", ge=5.0, le=600.0
    )

    # PayPal Integration
    paypal_client_id: str = Field(default="", alias="PAYPAL_CLIENT_ID")
    paypal_client_secret: SecretStr = Field(default=SecretStr(""), alias="PAYPAL_CLIENT_SECRET")
    paypal_base_url: str = Field(
        default="https://api-m.sandbox.paypal.com", alias="PAYPAL_BASE_URL"
    )
    paypal_webhook_id: str = Field(default="", alias="PAYPAL_WEBHOOK_ID")
    paypal_timeout_seconds: float = Field(
        default=20.0, alias="PAYPAL_TIMEOUT_SECONDS", ge=1.0, le=120.0
    )

    # Product Discovery Integration
    channel3_api_key: SecretStr = Field(default=SecretStr(""), alias="CHANNEL3_API_KEY")
    channel3_base_url: str = Field(
        default="https://api.trychannel3.com/v1", alias="CHANNEL3_BASE_URL"
    )
    enable_test_product_fixtures: bool = Field(
        default=False, alias="ENABLE_TEST_PRODUCT_FIXTURES"
    )

    # CORS & Rate Limiting
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"], alias="CORS_ORIGINS"
    )
    frontend_base_url: str = Field(
        default="http://localhost:5173", alias="FRONTEND_BASE_URL"
    )
    rate_limit_auth_requests: int = Field(
        default=10, alias="RATE_LIMIT_AUTH_REQUESTS", ge=1, le=1000
    )
    rate_limit_auth_window_seconds: int = Field(
        default=60, alias="RATE_LIMIT_AUTH_WINDOW_SECONDS", ge=1, le=3600
    )
    rate_limit_api_requests: int = Field(
        default=120, alias="RATE_LIMIT_API_REQUESTS", ge=10, le=10000
    )
    rate_limit_api_window_seconds: int = Field(
        default=60, alias="RATE_LIMIT_API_WINDOW_SECONDS", ge=1, le=3600
    )
    max_request_body_bytes: int = Field(
        default=1_048_576, alias="MAX_REQUEST_BODY_BYTES", ge=1024, le=52_428_800
    )
    request_timeout_seconds: float = Field(
        default=150.0, alias="REQUEST_TIMEOUT_SECONDS", ge=5.0, le=300.0
    )
    product_cache_ttl_seconds: int = Field(
        default=60, alias="PRODUCT_CACHE_TTL_SECONDS", ge=0, le=3600
    )
    expose_api_docs_in_prod: bool = Field(
        default=False, alias="EXPOSE_API_DOCS_IN_PROD"
    )
    default_currency: str = Field(default="USD", alias="DEFAULT_CURRENCY")
    default_single_tx_limit: str = Field(default="500.00", alias="DEFAULT_SINGLE_TX_LIMIT")
    default_daily_tx_limit: str = Field(default="1500.00", alias="DEFAULT_DAILY_TX_LIMIT")

    # Multi-Currency Exchange Rate Service
    exchange_rate_base_url: str = Field(
        default="https://api.frankfurter.dev/v1", alias="EXCHANGE_RATE_BASE_URL"
    )
    exchange_rate_api_key: SecretStr = Field(
        default=SecretStr(""), alias="EXCHANGE_RATE_API_KEY"
    )
    exchange_rate_cache_ttl_seconds: int = Field(
        default=900, alias="EXCHANGE_RATE_CACHE_TTL_SECONDS", ge=0, le=86400
    )
    exchange_rate_timeout_seconds: float = Field(
        default=8.0, alias="EXCHANGE_RATE_TIMEOUT_SECONDS", ge=1.0, le=60.0
    )
    paypal_settlement_currency: str = Field(
        default="USD", alias="PAYPAL_SETTLEMENT_CURRENCY"
    )

    # Ephemeral runtime secrets used ONLY when non-production env omits secrets
    _ephemeral_secret_key: str = ""
    _ephemeral_jwt_secret_key: str = ""

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_flag(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug"}:
            return True
        if normalized in {"", "0", "false", "no", "off", "release", "prod", "production"}:
            return False
        raise ValueError(f"DEBUG must be a valid boolean flag, got '{value}'")

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"development", "testing", "staging", "production"}
        if normalized not in allowed:
            raise ValueError(f"APP_ENV must be one of {sorted(allowed)}, got '{value}'")
        return normalized

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return ["http://localhost:5173"]
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                import json

                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(origin).strip() for origin in parsed if str(origin).strip()]
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        raise ValueError("CORS_ORIGINS must be a comma-separated string or JSON list")

    @field_validator("default_currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        code = value.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError("DEFAULT_CURRENCY must be a 3-letter ISO-4217 code")
        return code

    @field_validator("paypal_base_url")
    @classmethod
    def validate_paypal_base_url(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("PAYPAL_BASE_URL must be a valid HTTP(S) URL")
        return cleaned

    @field_validator("frontend_base_url")
    @classmethod
    def validate_frontend_base_url(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("FRONTEND_BASE_URL must be a valid HTTP(S) URL")
        return cleaned

    @model_validator(mode="after")
    def validate_environment_security(self) -> "Settings":
        # Never permit live PayPal endpoint outside production.
        if self.app_env != "production" and "api-m.paypal.com" in self.paypal_base_url.lower():
            raise ConfigurationError(
                "Live PayPal endpoint is forbidden when APP_ENV is not 'production'. "
                "Use https://api-m.sandbox.paypal.com."
            )

        if self.app_env == "production":
            if self.debug:
                raise ConfigurationError(
                    "DEBUG must be false when APP_ENV is 'production'."
                )
            if len(self.secret_key.get_secret_value().strip()) < 32:
                raise ConfigurationError(
                    "SECRET_KEY must be configured with at least 32 characters in production."
                )
            if len(self.jwt_secret_key.get_secret_value().strip()) < 32:
                raise ConfigurationError(
                    "JWT_SECRET_KEY must be configured with at least 32 characters in production."
                )
            db_url_lower = self.database_url.strip().lower()
            if not db_url_lower:
                raise ConfigurationError("DATABASE_URL must be configured in production.")
            if db_url_lower.startswith("sqlite"):
                raise ConfigurationError(
                    "SQLite DATABASE_URL is forbidden in production; configure PostgreSQL."
                )
            if "sandbox.paypal.com" in self.paypal_base_url.lower():
                raise ConfigurationError(
                    "PayPal Sandbox URL cannot be used when APP_ENV is 'production'."
                )
            if not self.is_paypal_configured or not self.paypal_webhook_id.strip():
                raise ConfigurationError(
                    "PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, and PAYPAL_WEBHOOK_ID must be configured in production."
                )
            if not self.is_nvidia_configured:
                raise ConfigurationError(
                    "NVIDIA_API_KEY and NVIDIA_MODEL must be configured in production."
                )
            if self.enable_test_product_fixtures:
                raise ConfigurationError(
                    "ENABLE_TEST_PRODUCT_FIXTURES must be false in production."
                )
            if "*" in self.cors_origins:
                raise ConfigurationError("Wildcard CORS_ORIGINS is not allowed in production.")
            for origin in self.cors_origins:
                parsed_origin = urlparse(origin)
                host = (parsed_origin.hostname or "").lower()
                if parsed_origin.scheme != "https" or host in {"localhost", "127.0.0.1", "0.0.0.0"}:
                    raise ConfigurationError(
                        f"Production CORS_ORIGINS must contain only approved HTTPS origins (invalid: '{origin}')."
                    )
            parsed_fe = urlparse(self.frontend_base_url)
            if parsed_fe.scheme != "https" or (parsed_fe.hostname or "").lower() in {"localhost", "127.0.0.1"}:
                raise ConfigurationError(
                    "FRONTEND_BASE_URL must use a non-local HTTPS URL in production."
                )
        else:
            if not self.secret_key.get_secret_value().strip():
                self._ephemeral_secret_key = secrets.token_urlsafe(48)
            if not self.jwt_secret_key.get_secret_value().strip():
                self._ephemeral_jwt_secret_key = secrets.token_urlsafe(48)

        return self

    def get_secret_key(self) -> str:
        val = self.secret_key.get_secret_value().strip()
        return val if val else self._ephemeral_secret_key

    def get_jwt_secret_key(self) -> str:
        val = self.jwt_secret_key.get_secret_value().strip()
        return val if val else self._ephemeral_jwt_secret_key

    @property
    def uses_ephemeral_secrets(self) -> bool:
        return bool(self._ephemeral_secret_key or self._ephemeral_jwt_secret_key)

    @property
    def is_database_configured(self) -> bool:
        return bool(self.database_url.strip())

    @property
    def is_nvidia_configured(self) -> bool:
        return bool(
            self.nvidia_api_key.get_secret_value().strip() and self.nvidia_model.strip()
        )

    @property
    def is_mistral_configured(self) -> bool:
        return bool(
            self.mistral_api_key.get_secret_value().strip() and self.mistral_model.strip()
        )

    @property
    def is_groq_configured(self) -> bool:
        return bool(
            self.groq_api_key.get_secret_value().strip() and self.groq_model.strip()
        )

    @property
    def is_paypal_configured(self) -> bool:
        return bool(
            self.paypal_client_id.strip()
            and self.paypal_client_secret.get_secret_value().strip()
        )

    @property
    def is_channel3_configured(self) -> bool:
        return bool(self.channel3_api_key.get_secret_value().strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings loaded from environment."""
    return Settings()


def clear_settings_cache() -> None:
    """Clear settings cache (used in tests when overriding environment variables)."""
    get_settings.cache_clear()
