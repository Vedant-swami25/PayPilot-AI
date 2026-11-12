/**
 * Format numeric/string monetary values for display without altering backend Decimal authority.
 */
export function formatCurrency(amount, currency = "USD") {
  if (amount === null || amount === undefined || amount === "") {
    return "—";
  }
  const numeric = Number(amount);
  const code = (currency || "USD").toUpperCase();
  if (!Number.isFinite(numeric)) {
    return `${amount} ${code}`;
  }

  try {
    const locale = code === "INR" ? "en-IN" : undefined;
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: code,
      minimumFractionDigits: code === "JPY" ? 0 : 2,
      maximumFractionDigits: code === "JPY" ? 0 : 2,
    }).format(numeric);
  } catch {
    return `${numeric.toFixed(2)} ${code}`;
  }
}

/**
 * Resolve normalized display vs original merchant pricing fields from API product/item payloads.
 */
export function getDisplayMoney(item) {
  if (!item) {
    return {
      displayPrice: null,
      displayCurrency: "USD",
      originalPrice: null,
      originalCurrency: "USD",
      hasConversion: false,
      exchangeRate: null,
      exchangeRateTimestamp: null,
    };
  }

  const baseOriginalPrice =
    item.original_price ?? item.price ?? item.recommended_price ?? null;
  const baseOriginalCurrency = (
    item.original_currency ||
    item.currency ||
    "USD"
  ).toUpperCase();

  const resolvedDisplayPrice =
    item.display_price ?? item.recommended_price ?? item.price ?? null;
  const resolvedDisplayCurrency = (
    item.display_currency ||
    item.currency ||
    baseOriginalCurrency
  ).toUpperCase();

  const hasConversion =
    baseOriginalPrice !== null &&
    resolvedDisplayPrice !== null &&
    baseOriginalCurrency !== resolvedDisplayCurrency;

  return {
    displayPrice: resolvedDisplayPrice,
    displayCurrency: resolvedDisplayCurrency,
    originalPrice: baseOriginalPrice,
    originalCurrency: baseOriginalCurrency,
    hasConversion,
    exchangeRate: item.exchange_rate ?? null,
    exchangeRateTimestamp: item.exchange_rate_timestamp ?? null,
  };
}

