import React from "react";
import { CheckCircle2, ShieldAlert, ShieldCheck, Store } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatCurrency, getDisplayMoney } from "@/utils/formatCurrency";

export function RecommendationCard({
  recommendation,
  securityAssessment = null,
  onApproveAndCheckout = null,
  onCompare = null,
  approving = false,
  alreadyApproved = false,
  disabled = false,
}) {
  if (!recommendation) return null;

  const isBlocked = Boolean(securityAssessment?.block_execution);
  const {
    displayPrice,
    displayCurrency,
    originalPrice,
    originalCurrency,
    hasConversion,
  } = getDisplayMoney(recommendation);

  return (
    <Card glow className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <Badge tone="emerald">Recommended Pick</Badge>
            {securityAssessment && (
              <Badge tone={isBlocked ? "red" : "emerald"}>
                {isBlocked ? (
                  <ShieldAlert className="h-3 w-3" />
                ) : (
                  <ShieldCheck className="h-3 w-3" />
                )}
                <span>
                  {isBlocked ? "Limit Check: Blocked" : "Spending Check: Passed"}
                </span>
              </Badge>
            )}
          </div>
          <h3 className="text-lg font-semibold text-text-primary">
            {recommendation.recommended_product_name}
          </h3>
          <p className="mt-0.5 inline-flex items-center gap-1.5 text-xs text-text-secondary">
            <Store className="h-3.5 w-3.5 text-text-muted" />
            Merchant: <strong className="text-text-primary">{recommendation.merchant}</strong>
          </p>
        </div>

        <div className="text-right">
          <p className="text-2xl font-semibold text-text-primary tabular-nums">
            {formatCurrency(displayPrice, displayCurrency)}
          </p>
          <p className="text-[11px] text-text-muted uppercase">
            {displayCurrency}
          </p>
          {hasConversion && (
            <p className="text-[11px] text-text-secondary tabular-nums mt-0.5">
              Merchant: {formatCurrency(originalPrice, originalCurrency)} {originalCurrency}
            </p>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-border-subtle bg-bg-primary p-3.5 text-sm text-text-secondary leading-relaxed">
        {recommendation.rationale}
      </div>

      {recommendation.trade_offs?.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">
            Key Trade-Offs
          </p>
          <ul className="space-y-1">
            {recommendation.trade_offs.map((t, idx) => (
              <li key={idx} className="text-xs text-text-secondary flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#16A36A] shrink-0" />
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {securityAssessment && (
        <div
          className={`rounded-lg border p-3.5 text-xs ${
            isBlocked
              ? "border-[#FECDCA] bg-[#FEF3F2] text-[#B42318] dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200"
              : "border-[#ABEFC6] bg-[#ECFDF3] text-[#067647] dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200"
          }`}
        >
          <p className="font-semibold mb-1">
            {isBlocked ? "Blocked by Spending Limit" : "Purchase Protection Verified"}
          </p>
          <p className="text-text-secondary">{securityAssessment.assessment_summary}</p>
          {securityAssessment.policy_violations?.length > 0 && (
            <ul className="mt-2 space-y-1">
              {securityAssessment.policy_violations.map((v, i) => (
                <li key={i}>• {v}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-end gap-2.5 pt-2 border-t border-border-subtle">
        {onCompare && (
          <Button variant="secondary" size="sm" onClick={onCompare}>
            View Comparison
          </Button>
        )}
        {onApproveAndCheckout && (
          <Button
            size="sm"
            variant="emerald"
            loading={approving}
            disabled={isBlocked || disabled}
            onClick={onApproveAndCheckout}
            icon={<CheckCircle2 className="h-4 w-4" />}
          >
            {alreadyApproved
              ? "Continue to PayPal Checkout"
              : "Approve & Checkout with PayPal"}
          </Button>
        )}
      </div>
    </Card>
  );
}
