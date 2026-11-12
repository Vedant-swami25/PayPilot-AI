import React, { useState } from "react";
import { ShieldCheck, AlertTriangle, Lock, ShoppingBag, Check } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatCurrency, getDisplayMoney } from "@/utils/formatCurrency";

export function PaymentApproval({
  product,
  workflow,
  quote = null,
  quoteLoading = false,
  quoteError = "",
  quantity = 1,
  onQuantityChange,
  spendingLimit,
  onAuthorizeOrder,
  isAuthorizing = false,
  errorMessage = "",
}) {
  const [confirmedIntent, setConfirmedIntent] = useState(false);

  if (!product) return null;

  const security = workflow?.security_assessment || {};
  const riskLevel = (security.risk_level || "LOW").toUpperCase();
  const isSecurityBlocked =
    workflow?.status === "BLOCKED_BY_SECURITY" ||
    security.block_execution === true ||
    security.blocked === true ||
    security.allowed === false;
  const currencyBlocked = Boolean(quoteError) || quote?.can_checkout === false;
  const isBlocked = isSecurityBlocked || currencyBlocked;
  const securitySummary = security.assessment_summary || security.summary || "";
  const securityIssues = security.policy_violations || security.warnings || [];

  const qtyNum = Math.max(1, Number(quantity) || 1);
  const productMoney = getDisplayMoney(product);
  const originalCurrency = (quote?.original_currency || productMoney.originalCurrency).toUpperCase();
  const originalUnitPrice = Number(quote?.original_unit_price ?? productMoney.originalPrice ?? 0);
  const originalSubtotal =
    quote?.original_amount != null
      ? Number(quote.original_amount)
      : originalUnitPrice * qtyNum;

  const displayCurrency = (quote?.display_currency || productMoney.displayCurrency).toUpperCase();
  const displaySubtotal =
    quote?.display_amount != null
      ? Number(quote.display_amount)
      : Number(productMoney.displayPrice ?? originalUnitPrice) * qtyNum;

  const payableCurrency = (
    quote?.payable_currency ||
    workflow?.approved_currency ||
    originalCurrency
  ).toUpperCase();
  const payableSubtotal =
    quote?.payable_amount != null
      ? Number(quote.payable_amount)
      : workflow?.approved_amount != null && qtyNum === 1
        ? Number(workflow.approved_amount)
        : originalSubtotal;

  const singleLimit = spendingLimit?.max_single_transaction
    ? Number(spendingLimit.max_single_transaction)
    : null;
  const currencyBlockingReason =
    quoteError ||
    quote?.blocking_reason ||
    (currencyBlocked
      ? "Merchant price and PayPal payment currency could not be reconciled safely."
      : "");

  return (
    <Card className="space-y-5">
      <CardHeader
        title="Purchase Confirmation"
        subtitle="Review verified product details, amount breakdown, and spending limits before creating a PayPal order."
        action={
          <Badge tone={isBlocked ? "red" : riskLevel === "HIGH" ? "amber" : "emerald"} dot>
            {isSecurityBlocked
              ? "Blocked by Security"
              : currencyBlocked
                ? "Checkout Blocked"
                : "Spending Check: Passed"}
          </Badge>
        }
      />

      {/* Selected Product Summary */}
      <div className="flex flex-col sm:flex-row gap-4 rounded-xl border border-border-subtle bg-bg-secondary p-4">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name}
            className="h-20 w-20 rounded-xl object-contain p-1.5 border border-border-subtle shrink-0 bg-white dark:bg-slate-900"
          />
        ) : (
          <div className="h-20 w-20 rounded-xl border border-border-subtle bg-bg-card flex items-center justify-center shrink-0">
            <ShoppingBag className="h-6 w-6 text-text-muted" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h4 className="text-sm font-semibold text-text-primary leading-snug">
                {product.name}
              </h4>
              <p className="text-xs text-text-secondary mt-0.5">
                Merchant:{" "}
                <span className="font-medium text-text-primary">
                  {product.merchant || "Verified Seller"}
                </span>
                {product.availability ? ` • ${product.availability}` : ""}
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm font-mono font-semibold text-text-primary tabular-nums">
                {formatCurrency(originalUnitPrice, originalCurrency)}
              </p>
              <p className="text-[11px] text-text-secondary">
                Merchant unit price ({originalCurrency})
              </p>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-border-subtle">
            <div className="flex items-center gap-2 text-xs text-text-secondary">
              <label htmlFor="checkout-qty" className="font-medium text-text-primary">
                Quantity:
              </label>
              <input
                id="checkout-qty"
                type="number"
                min={1}
                max={20}
                value={quantity}
                onChange={(e) => {
                  const val = Math.max(1, Math.min(20, Number(e.target.value) || 1));
                  onQuantityChange?.(val);
                }}
                disabled={isAuthorizing || isBlocked}
                className="w-16 rounded-lg border border-border-subtle bg-bg-card px-2 py-1 text-xs font-mono text-text-primary focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30 focus:border-[#16A36A]"
              />
            </div>

            <div className="text-right">
              <p className="text-xs text-text-secondary">
                Merchant Subtotal:{" "}
                <span className="font-mono font-bold text-text-primary tabular-nums">
                  {formatCurrency(originalSubtotal, originalCurrency)} {originalCurrency}
                </span>
              </p>
              {displayCurrency !== originalCurrency && (
                <p className="text-xs font-mono text-text-secondary mt-0.5 tabular-nums">
                  Display Est.: {formatCurrency(displaySubtotal, displayCurrency)} {displayCurrency}
                </p>
              )}
              {workflow?.approved_amount != null && (
                <p className="text-xs font-mono font-semibold text-[#067647] dark:text-emerald-400 mt-0.5 tabular-nums">
                  Approved Ref: {formatCurrency(workflow.approved_amount, payableCurrency)} {payableCurrency}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Amount Breakdown */}
      <div className="rounded-xl border border-border-subtle bg-bg-card p-4 space-y-2 text-xs">
        <p className="font-semibold text-text-primary">Amount Breakdown</p>
        <div className="flex items-center justify-between text-text-secondary">
          <span>
            Merchant Price ({formatCurrency(originalUnitPrice, originalCurrency)} {originalCurrency} × {qtyNum})
          </span>
          <span className="font-mono text-text-primary tabular-nums">
            {formatCurrency(originalSubtotal, originalCurrency)} {originalCurrency}
          </span>
        </div>
        {displayCurrency !== originalCurrency && (
          <div className="flex items-center justify-between text-text-secondary">
            <span>
              Converted Display Estimate ({displayCurrency})
              {quote?.display_exchange_rate
                ? ` @ ${Number(quote.display_exchange_rate).toFixed(2)}`
                : ""}
            </span>
            <span className="font-mono text-text-primary tabular-nums">
              {formatCurrency(displaySubtotal, displayCurrency)} {displayCurrency}
            </span>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-border-subtle pt-2 font-semibold text-text-primary">
          <span>Authoritative PayPal Charge ({payableCurrency})</span>
          <span className="font-mono tabular-nums">
            {quoteLoading
              ? "Verifying..."
              : `${formatCurrency(payableSubtotal, payableCurrency)} ${payableCurrency}`}
          </span>
        </div>
        {(displayCurrency !== payableCurrency || quote?.payment_conversion_required) && (
          <p className="text-[11px] text-text-secondary pt-1 leading-relaxed">
            {quote?.payment_conversion_required
              ? `Merchant currency (${originalCurrency}) was converted to supported PayPal settlement currency (${payableCurrency}) using live FX rate ${Number(quote.payment_exchange_rate).toFixed(4)}.`
              : `PayPal executes this payment in ${payableCurrency} (${formatCurrency(payableSubtotal, payableCurrency)}). The ${displayCurrency} amount is shown for display reference only.`}
          </p>
        )}
      </div>

      {currencyBlockingReason && (
        <div
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 dark:border-rose-500/35 dark:bg-rose-500/10 p-3.5 text-xs text-[#B42318] dark:text-rose-300 flex items-start gap-2.5"
        >
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-[#D92D20]" />
          <div>
            <p className="font-semibold">Currency Conversion / Payment Verification Blocked</p>
            <p className="mt-0.5">{currencyBlockingReason}</p>
          </div>
        </div>
      )}

      {/* Security Policy & Limits Check */}
      <div
        className={`rounded-xl border p-4 space-y-2.5 text-xs ${
          isBlocked
            ? "border-rose-200 bg-rose-50 dark:border-rose-500/30 dark:bg-rose-500/10"
            : "border-border-subtle bg-bg-secondary"
        }`}
      >
        <div className="flex items-center gap-2 font-semibold text-text-primary">
          {isBlocked ? (
            <AlertTriangle className="h-4 w-4 text-[#D92D20]" />
          ) : (
            <ShieldCheck className="h-4 w-4 text-[#16A36A]" />
          )}
          <span>Spending Limits & Protection</span>
        </div>
        {securitySummary && (
          <p className="text-text-secondary leading-relaxed">{securitySummary}</p>
        )}
        {Array.isArray(securityIssues) && securityIssues.length > 0 && (
          <ul className="space-y-1 text-amber-800 dark:text-amber-300 list-disc pl-4">
            {securityIssues.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        )}
        {singleLimit != null && (
          <p className="text-text-secondary">
            Account Single-Transaction Limit:{" "}
            <span className="font-mono font-semibold text-text-primary">
              {formatCurrency(singleLimit, spendingLimit?.currency || payableCurrency)}
            </span>
          </p>
        )}
      </div>

      {errorMessage && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 dark:border-rose-500/35 dark:bg-rose-500/10 p-3 text-xs text-[#B42318] dark:text-rose-300">
          {errorMessage}
        </div>
      )}

      {/* Explicit Consent Checkbox */}
      {!isBlocked && (
        <label className="flex items-start gap-3 cursor-pointer rounded-xl border border-border-subtle bg-bg-secondary p-3.5 hover:border-[#16A36A]/50 transition-colors">
          <span
            className={`relative mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors ${
              confirmedIntent
                ? "border-[#16A36A] bg-[#16A36A] text-white"
                : "border-slate-400 dark:border-slate-600 bg-bg-card"
            }`}
          >
            <input
              type="checkbox"
              checked={confirmedIntent}
              onChange={(e) => setConfirmedIntent(e.target.checked)}
              className="sr-only"
            />
            {confirmedIntent && <Check className="h-3 w-3" strokeWidth={3} />}
          </span>
          <span className="text-xs text-text-secondary leading-relaxed">
            I verify the product, merchant, and quantity above and authorize PayPilot to create a backend-verified PayPal order for my interactive approval.
          </span>
        </label>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        <span className="inline-flex items-center gap-1.5 text-xs text-text-secondary">
          <Lock className="h-3.5 w-3.5 text-[#16A36A]" />
          Capture happens only after PayPal authorization
        </span>
        <Button
          variant="primary"
          size="lg"
          disabled={!confirmedIntent || isBlocked || quoteLoading}
          loading={isAuthorizing}
          onClick={onAuthorizeOrder}
        >
          Authorize & Create PayPal Order
        </Button>
      </div>
    </Card>
  );
}
