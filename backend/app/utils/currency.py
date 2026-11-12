from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

SUPPORTED_CURRENCIES: dict[str, int] = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "CAD": 2,
    "AUD": 2,
    "INR": 2,
    "SGD": 2,
    "JPY": 0,
}

# Currencies supported by PayPal Orders v2 REST API on standard international accounts.
# INR is intentionally excluded so INR display prices are never submitted as INR to PayPal.
PAYPAL_SUPPORTED_CURRENCIES: frozenset[str] = frozenset(
    {"USD", "EUR", "GBP", "CAD", "AUD", "SGD", "JPY"}
)


def is_paypal_supported_currency(currency: str) -> bool:
    """Return True when PayPal Orders API natively accepts the given currency code."""
    try:
        code = validate_currency_code(currency)
    except CurrencyError:
        return False
    return code in PAYPAL_SUPPORTED_CURRENCIES


def quantize_exchange_rate(rate: Decimal | str | float) -> Decimal:
    """Quantize an FX rate cleanly to 6 decimal places without float artifacts."""
    dec = rate if isinstance(rate, Decimal) else to_decimal(rate)
    return dec.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


class CurrencyError(ValueError):
    """Raised when a currency code or monetary amount is invalid."""


def validate_currency_code(currency: str) -> str:
    """Validate and normalize a 3-letter ISO-4217 currency code."""
    code = (currency or "").strip().upper()
    if code not in SUPPORTED_CURRENCIES:
        raise CurrencyError(
            f"Unsupported currency '{currency}'. Supported: {sorted(SUPPORTED_CURRENCIES)}"
        )
    return code


def to_decimal(value: Any, *, allow_zero: bool = False) -> Decimal:
    """Safely convert input to finite Decimal without floating-point rounding drift."""
    if isinstance(value, bool):
        raise CurrencyError("Boolean cannot be converted to a monetary amount.")
    if isinstance(value, float):
        # Convert via str() to avoid binary float representation artifacts
        raw = str(value)
    else:
        raw = str(value).strip()

    try:
        dec = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise CurrencyError(f"Invalid monetary amount: '{value}'") from exc

    if not dec.is_finite():
        raise CurrencyError("Monetary amount must be finite.")
    if allow_zero:
        if dec < Decimal("0"):
            raise CurrencyError("Monetary amount cannot be negative.")
    elif dec <= Decimal("0"):
        raise CurrencyError("Monetary amount must be greater than zero.")

    return dec


def quantize_amount(amount: Decimal | str | int, currency: str = "USD") -> Decimal:
    """Quantize a monetary Decimal to the currency's minor-unit precision."""
    code = validate_currency_code(currency)
    decimals = SUPPORTED_CURRENCIES[code]
    dec = amount if isinstance(amount, Decimal) else to_decimal(amount, allow_zero=True)
    quantum = Decimal("1") if decimals == 0 else Decimal(f"1e-{decimals}")
    return dec.quantize(quantum, rounding=ROUND_HALF_UP)


def format_paypal_amount(amount: Decimal, currency: str = "USD") -> str:
    """Format Decimal monetary amount as string expected by PayPal Orders API v2."""
    quantized = quantize_amount(amount, currency)
    return str(quantized)


def calculate_order_total(
    unit_price: Decimal | str, quantity: int, currency: str = "USD"
) -> Decimal:
    """Calculate backend-authoritative order total using exact Decimal arithmetic."""
    if quantity < 1 or quantity > 100:
        raise CurrencyError("Quantity must be between 1 and 100.")
    unit_dec = to_decimal(unit_price)
    total = unit_dec * Decimal(quantity)
    return quantize_amount(total, currency)

