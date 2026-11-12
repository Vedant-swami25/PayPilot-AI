import React from "react";
import { CheckCircle2, Clock, ShieldAlert, XCircle, RotateCcw } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { PAYMENT_STATUS_META } from "@/utils/constants";

const STEPS = [
  { key: "CREATED", label: "Order Created" },
  { key: "PENDING_APPROVAL", label: "PayPal Approval" },
  { key: "APPROVED", label: "Authorized" },
  { key: "COMPLETED", label: "Captured" },
];

function getStepIndex(status) {
  if (status === "COMPLETED") return 3;
  if (status === "CAPTURE_PENDING" || status === "APPROVED") return 2;
  if (status === "PENDING_APPROVAL") return 1;
  return 0;
}

export function PaymentStatusBadge({ status }) {
  const meta = PAYMENT_STATUS_META[status] || {
    label: status || "Unknown",
    tone: "slate",
  };
  const isPulse = status === "PENDING_APPROVAL" || status === "CAPTURE_PENDING";
  return (
    <Badge tone={meta.tone} dot pulse={isPulse}>
      {meta.label}
    </Badge>
  );
}

export function PaymentStatus({ order }) {
  if (!order) return null;
  const status = order.status;
  const isTerminalError =
    status === "FAILED" || status === "CANCELLED" || status === "REFUNDED";
  const activeStep = getStepIndex(status);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {status === "COMPLETED" ? (
            <CheckCircle2 className="h-5 w-5 text-[#12B76A]" />
          ) : status === "FAILED" ? (
            <ShieldAlert className="h-5 w-5 text-[#D92D20]" />
          ) : status === "CANCELLED" ? (
            <XCircle className="h-5 w-5 text-text-secondary" />
          ) : status === "REFUNDED" ? (
            <RotateCcw className="h-5 w-5 text-amber-600 dark:text-amber-400" />
          ) : (
            <Clock className="h-5 w-5 text-[#101828] dark:text-slate-200" />
          )}
          <span className="text-sm font-semibold text-text-primary">
            Payment Verification Status
          </span>
        </div>
        <PaymentStatusBadge status={status} />
      </div>

      {!isTerminalError && (
        <div className="grid grid-cols-4 gap-2">
          {STEPS.map((step, idx) => {
            const done = idx < activeStep || status === "COMPLETED";
            const current = idx === activeStep && status !== "COMPLETED";
            return (
              <div key={step.key} className="space-y-1.5">
                <div
                  className={`h-1.5 rounded-full transition-colors ${
                    done
                      ? "bg-[#16A36A]"
                      : current
                      ? "bg-[#101828] dark:bg-emerald-400"
                      : "bg-slate-200 dark:bg-slate-700"
                  }`}
                />
                <p
                  className={`text-[11px] font-medium truncate ${
                    done
                      ? "text-[#067647] dark:text-emerald-400"
                      : current
                      ? "text-text-primary font-semibold"
                      : "text-text-muted"
                  }`}
                >
                  {step.label}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
