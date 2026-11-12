import React, { useMemo, useState } from "react";
import { PayPalScriptProvider, PayPalButtons } from "@paypal/react-paypal-js";
import {
  ExternalLink,
  RefreshCw,
  ShieldCheck,
  XCircle,
  AlertCircle,
  CreditCard,
  Lock,
  Copy,
  Check,
  Store,
} from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { ConfirmationDialog } from "@/components/ui/Modal";
import { PaymentStatus } from "@/components/payments/PaymentStatus";
import { PaymentSuccessAnimation } from "@/components/animations/PaymentSuccessAnimation";
import { PAYPAL_CLIENT_ID } from "@/utils/constants";
import { formatCurrency } from "@/utils/formatCurrency";
import { formatDateTime } from "@/utils/formatDate";
import { useAppStore } from "@/store/useAppStore";

export function PayPalCheckout({
  order,
  isSyncing = false,
  onSyncOrder,
  onCapturePayment,
  isCapturing = false,
  onCancelOrder,
  isCancelling = false,
}) {
  const pushToast = useAppStore((s) => s.pushToast);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [sdkError, setSdkError] = useState("");
  const [copiedId, setCopiedId] = useState(false);

  const handleCopyId = (id) => {
    if (!id) return;
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(id).catch(() => {});
    }
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const sdkOptions = useMemo(() => {
    if (!PAYPAL_CLIENT_ID || !order?.currency) return null;
    return {
      "client-id": PAYPAL_CLIENT_ID,
      currency: order.currency,
      intent: "capture",
    };
  }, [order?.currency]);

  if (!order) return null;

  if (order.status === "COMPLETED") {
    return (
      <div className="space-y-4">
        <PaymentSuccessAnimation
          transactionId={order.id}
          paypalOrderId={order.paypal_order_id}
          amount={order.amount}
          currency={order.currency}
        />
        <Card>
          <PaymentStatus order={order} />
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs border-t border-border-subtle pt-4">
            <div>
              <span className="text-text-secondary">Merchant</span>
              <p className="font-medium text-text-primary mt-0.5">
                {order.merchant || "Verified Seller"}
              </p>
            </div>
            <div>
              <span className="text-text-secondary">Quantity</span>
              <p className="font-mono font-medium text-text-primary mt-0.5">
                {order.quantity}
              </p>
            </div>
            <div>
              <span className="text-text-secondary">Approved / Updated</span>
              <p className="font-medium text-text-primary mt-0.5">
                {formatDateTime(order.approved_at || order.updated_at)}
              </p>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  const allowed = order.allowed_actions || [];
  const canCapture =
    allowed.includes("capture") || order.status === "APPROVED";
  const canCancel =
    allowed.includes("cancel") ||
    ["CREATED", "PENDING_APPROVAL", "APPROVED"].includes(order.status);

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title="PayPal Checkout & Capture"
          subtitle="Server-verified PayPal order. Funds are captured only after PayPal confirms your authorization."
          action={
            <Button
              variant="ghost"
              size="xs"
              icon={<RefreshCw className={`h-3.5 w-3.5 ${isSyncing ? "animate-spin" : ""}`} />}
              onClick={() => onSyncOrder?.()}
              disabled={isSyncing}
            >
              Sync Status
            </Button>
          }
        />

        <PaymentStatus order={order} />

        {/* Polished Authoritative Order Summary Card */}
        <div className="mt-5 overflow-hidden rounded-xl border border-border-subtle bg-bg-secondary/60 dark:bg-bg-card/40 backdrop-blur-sm shadow-xs">
          {/* Top Hero Banner: Prominent Order Amount & Verified Protection */}
          <div className="p-4 sm:p-5 border-b border-border-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-gradient-to-r from-bg-secondary/90 via-bg-card/40 to-bg-secondary/90 dark:from-slate-900/60 dark:via-slate-900/30 dark:to-slate-900/60">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
                  Order Amount
                </span>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-400 border border-emerald-500/20">
                  <ShieldCheck className="h-3 w-3" />
                  Server Verified
                </span>
              </div>
              <div className="mt-1 flex items-baseline gap-2">
                <p className="text-2xl sm:text-3xl font-mono font-bold tracking-tight text-text-primary tabular-nums">
                  {formatCurrency(order.amount, order.currency)}
                </p>
                <span className="text-xs font-mono font-semibold text-text-muted uppercase">
                  {order.currency}
                </span>
              </div>

              {/* Multi-Currency Hints if Applicable */}
              {(order.original_amount &&
                order.original_currency &&
                order.original_currency !== order.currency) ||
              (order.display_amount &&
                order.display_currency &&
                order.display_currency !== order.currency) ? (
                <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-text-muted tabular-nums">
                  {order.original_amount &&
                    order.original_currency &&
                    order.original_currency !== order.currency && (
                      <span>
                        Merchant:{" "}
                        <span className="font-mono font-medium text-text-secondary">
                          {formatCurrency(order.original_amount, order.original_currency)}{" "}
                          {order.original_currency}
                        </span>
                      </span>
                    )}
                  {order.display_amount &&
                    order.display_currency &&
                    order.display_currency !== order.currency && (
                      <span>
                        Est. display:{" "}
                        <span className="font-mono font-medium text-text-secondary">
                          {formatCurrency(order.display_amount, order.display_currency)}{" "}
                          {order.display_currency}
                        </span>
                      </span>
                    )}
                </div>
              ) : null}
            </div>

            <div className="shrink-0 flex items-center gap-2 self-start sm:self-center">
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-border-subtle bg-bg-card/90 dark:bg-slate-800/80 px-3 py-1.5 text-xs text-text-secondary shadow-xs">
                <Lock className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                <span>Captured only upon approval</span>
              </span>
            </div>
          </div>

          {/* Balanced Metadata Tiles */}
          <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-border-subtle text-xs">
            {/* PayPal Order ID */}
            <div className="p-3.5 sm:p-4 space-y-1.5">
              <span className="text-[11px] font-medium text-text-secondary block">
                PayPal Order ID
              </span>
              <div className="flex items-center justify-between gap-2 bg-bg-card dark:bg-slate-900/60 p-1.5 rounded-lg border border-border-subtle">
                <code className="font-mono text-xs font-semibold text-text-primary truncate select-all pl-1">
                  {order.paypal_order_id || "Pending"}
                </code>
                {order.paypal_order_id && (
                  <button
                    type="button"
                    onClick={() => handleCopyId(order.paypal_order_id)}
                    title="Copy Order ID"
                    aria-label="Copy PayPal Order ID"
                    className="p-1 rounded text-text-muted hover:text-text-primary hover:bg-bg-secondary transition-colors shrink-0"
                  >
                    {copiedId ? (
                      <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                  </button>
                )}
              </div>
            </div>

            {/* Merchant */}
            <div className="p-3.5 sm:p-4 space-y-1.5">
              <span className="text-[11px] font-medium text-text-secondary block">
                Merchant
              </span>
              <div className="flex items-center gap-2 pt-0.5">
                <div className="h-6 w-6 rounded-md bg-bg-card dark:bg-slate-900/60 border border-border-subtle flex items-center justify-center text-text-muted shrink-0">
                  <Store className="h-3.5 w-3.5" />
                </div>
                <p className="font-medium text-text-primary truncate">
                  {order.merchant || "Verified Seller"}
                </p>
              </div>
            </div>

            {/* Approval State */}
            <div className="p-3.5 sm:p-4 space-y-1.5">
              <span className="text-[11px] font-medium text-text-secondary block">
                Approval State
              </span>
              <div className="pt-0.5 flex items-center gap-2">
                <span
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${
                    order.status === "COMPLETED" || order.approval_status === "COMPLETED"
                      ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20"
                      : order.status === "APPROVED" || order.approval_status === "APPROVED"
                      ? "bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20"
                      : "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20"
                  }`}
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
                  {order.approval_status || order.status}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Interactive PayPal JS SDK Buttons when awaiting user approval */}
        {["CREATED", "PENDING_APPROVAL"].includes(order.status) && (
          <div className="mt-5 space-y-4">
            {sdkOptions && order.paypal_order_id ? (
              <div className="rounded-xl border border-border-subtle bg-bg-card p-5 sm:p-6 shadow-card transition-colors">
                {/* Header with Title and Trust Badge */}
                <div className="flex flex-wrap items-center justify-between gap-2 pb-4 border-b border-border-subtle">
                  <div className="flex items-center gap-2.5">
                    <div className="h-8 w-8 rounded-lg bg-emerald-500/10 dark:bg-emerald-500/20 border border-emerald-500/20 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0">
                      <CreditCard className="h-4 w-4" />
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-text-primary leading-tight">
                        Complete PayPal Approval
                      </h4>
                      <p className="text-xs text-text-secondary mt-0.5">
                        Authorize in the official PayPal window to verify payment
                      </p>
                    </div>
                  </div>
                  <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-text-muted bg-bg-secondary px-2.5 py-1 rounded-full border border-border-subtle">
                    <ShieldCheck className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                    256-bit Encrypted
                  </span>
                </div>

                {/* Centered, proportional PayPal button container */}
                <div className="pt-5 pb-2">
                  <div className="w-full max-w-[360px] sm:max-w-[400px] mx-auto min-h-[110px] flex flex-col justify-center">
                    <PayPalScriptProvider options={sdkOptions}>
                      <PayPalButtons
                        style={{
                          layout: "vertical",
                          color: "blue",
                          shape: "rect",
                          label: "paypal",
                          height: 44,
                          tagline: false,
                        }}
                        createOrder={() => Promise.resolve(order.paypal_order_id)}
                        onApprove={async () => {
                          await onSyncOrder?.();
                          await onCapturePayment?.(order.id);
                        }}
                        onCancel={() => {
                          pushToast({
                            title: "PayPal popup closed",
                            description:
                              "Approval was cancelled in PayPal. No funds were captured.",
                            variant: "info",
                          });
                        }}
                        onError={(err) => {
                          setSdkError(
                            err?.message ||
                              "PayPal SDK encountered an issue loading checkout."
                          );
                        }}
                      />
                    </PayPalScriptProvider>
                  </div>
                  <p className="text-center text-[11px] text-text-muted mt-2">
                    Clicking PayPal opens a secure authorization dialog. Funds are captured only after your confirmation.
                  </p>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10 p-4 text-xs text-amber-800 dark:text-amber-200 flex items-start gap-2.5">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
                <div>
                  <p className="font-semibold">
                    PayPal JS Client ID (`VITE_PAYPAL_CLIENT_ID`) is not configured in frontend env.
                  </p>
                  <p className="mt-1 opacity-90">
                    Use the backend-provided PayPal Approval link below to authorize in PayPal directly, then click Sync & Capture.
                  </p>
                </div>
              </div>
            )}

            {sdkError && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 dark:border-rose-500/35 dark:bg-rose-500/10 p-3 text-xs text-[#B42318] dark:text-rose-300 space-y-1">
                <p className="font-semibold">{sdkError}</p>
                <p className="opacity-90">
                  If PayPal reported &ldquo;This seller doesn&apos;t accept payments in your currency&rdquo;, check that the Sandbox buyer and merchant are not both India (`IN`) accounts and enable foreign currency auto-conversion in Seller Payment Receiving Preferences.
                </p>
              </div>
            )}

            {order.order_snapshot?.paypal_merchant_country === "IN" && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10 p-3.5 text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2.5">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
                <div className="space-y-1">
                  <p className="font-semibold">
                    PayPal Sandbox Merchant Region Notice (India / IN)
                  </p>
                  <p className="opacity-90 leading-relaxed">
                    This order is billed in <span className="font-mono font-semibold">{order.currency}</span>, and your connected PayPal Sandbox Business merchant (
                    <span className="font-mono">{order.order_snapshot?.paypal_payee_merchant_id || "IN"}</span>
                    ) is registered in India (<span className="font-mono">IN</span>). PayPal blocks domestic IN buyer → IN seller transactions (showing &ldquo;This seller doesn&apos;t accept payments in your currency&rdquo;). To test <span className="font-mono">{order.currency}</span> checkout, approve with a non-India (e.g. US) Sandbox Personal buyer, or configure a US Sandbox Business facilitator with currency auto-conversion enabled.
                  </p>
                </div>
              </div>
            )}

            {/* Direct PayPal Approval Fallback */}
            {order.approval_url && (
              <div className="rounded-xl border border-dashed border-border-subtle bg-bg-secondary/40 dark:bg-slate-900/30 p-3.5 sm:p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-start sm:items-center gap-3">
                  <div className="h-7 w-7 rounded-md bg-bg-card dark:bg-slate-800 border border-border-subtle flex items-center justify-center text-text-muted shrink-0 mt-0.5 sm:mt-0">
                    <ExternalLink className="h-3.5 w-3.5" />
                  </div>
                  <div className="text-xs">
                    <p className="font-medium text-text-primary">
                      Popup blocked or prefer a full browser tab?
                    </p>
                    <p className="text-text-secondary text-[11px] mt-0.5">
                      Authorize directly on paypal.com, then return here to capture funds.
                    </p>
                  </div>
                </div>
                <a
                  href={order.approval_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group inline-flex items-center justify-center gap-1.5 rounded-lg border border-border-strong bg-bg-card hover:bg-bg-elevated px-3.5 py-1.5 text-xs font-medium text-text-primary transition-colors shrink-0 shadow-xs"
                >
                  <span>Open PayPal Approval</span>
                  <ExternalLink className="h-3.5 w-3.5 text-text-muted group-hover:text-text-primary transition-colors" />
                </a>
              </div>
            )}
          </div>
        )}

        {/* Capture / Cancel Action Bar */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-border-subtle pt-4">
          <div>
            {canCancel && (
              <Button
                variant="danger"
                size="sm"
                icon={<XCircle className="h-4 w-4" />}
                onClick={() => setCancelDialogOpen(true)}
                disabled={isCancelling || isCapturing}
              >
                Cancel Order
              </Button>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {canCapture ? (
              <Button
                variant="emerald"
                size="md"
                icon={<ShieldCheck className="h-4 w-4" />}
                loading={isCapturing}
                onClick={() => onCapturePayment?.(order.id)}
              >
                Capture Verified Payment
              </Button>
            ) : order.status === "PENDING_APPROVAL" ? (
              <Button
                variant="secondary"
                size="sm"
                icon={<RefreshCw className="h-4 w-4" />}
                loading={isSyncing}
                onClick={() => onSyncOrder?.()}
              >
                Verify PayPal Approval Status
              </Button>
            ) : null}
          </div>
        </div>
      </Card>

      <ConfirmationDialog
        open={cancelDialogOpen}
        onClose={() => setCancelDialogOpen(false)}
        onConfirm={async () => {
          await onCancelOrder?.(order.id);
          setCancelDialogOpen(false);
        }}
        title="Cancel Payment Order?"
        description="This cancels the PayPal order before any capture occurs. No charge will be finalized."
        confirmLabel="Yes, Cancel Order"
        tone="danger"
        loading={isCancelling}
      />
    </div>
  );
}
