import React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  CreditCard,
  Loader2,
  Scale,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { SHOPPING_STEP_META, WORKFLOW_STATUS_META } from "@/utils/constants";

const STAGE_SEQUENCE = [
  {
    key: "understanding",
    label: "Understanding requirements",
    icon: Sparkles,
    steps: ["LEAD_AGENT"],
  },
  {
    key: "searching",
    label: "Searching merchant listings",
    icon: Search,
    steps: ["DISCOVERY_AGENT"],
  },
  {
    key: "comparing",
    label: "Comparing prices & specs",
    icon: Scale,
    steps: ["COMPARISON_AGENT", "DECISION_AGENT"],
  },
  {
    key: "checking",
    label: "Checking spending limits",
    icon: ShieldCheck,
    steps: ["SECURITY_AGENT", "USER_APPROVAL"],
  },
  {
    key: "checkout",
    label: "PayPal checkout",
    icon: CreditCard,
    steps: ["PAYMENT_AGENT", "MONITORING_AGENT"],
  },
];

export function formatShoppingStepLabel(step) {
  if (!step) return null;
  if (SHOPPING_STEP_META[step]) return SHOPPING_STEP_META[step];
  return "Processing request";
}

export function deriveStageIndex(workflow, isSubmitting = false) {
  if (isSubmitting && !workflow) return 0;
  if (!workflow) return -1;

  const status = workflow.status;
  if (status === "COMPLETED" || status === "ORDER_CREATED" || status === "APPROVED") {
    return 4;
  }
  if (status === "AWAITING_USER_APPROVAL" || status === "BLOCKED_BY_SECURITY") {
    return 3;
  }
  if (status === "NO_PRODUCTS_FOUND" || status === "NEEDS_CLARIFICATION") {
    return 1;
  }

  const step = workflow.current_step;
  const idx = STAGE_SEQUENCE.findIndex((stage) => stage.steps.includes(step));
  if (idx >= 0) return idx;
  return status === "RUNNING" || status === "PENDING" ? 0 : -1;
}

export function ShoppingStatusBadge({ status, currentStep = null, showStage = false }) {
  const meta = WORKFLOW_STATUS_META[status] || {
    label: status || "Unknown",
    tone: "slate",
  };
  const stageText = showStage && currentStep ? formatShoppingStepLabel(currentStep) : null;

  return (
    <div className="inline-flex flex-wrap items-center gap-2">
      <Badge tone={meta.tone} dot pulse={status === "RUNNING" || status === "PENDING"}>
        {meta.label}
      </Badge>
      {stageText && status === "RUNNING" && (
        <span className="text-[11px] text-text-secondary">{stageText}</span>
      )}
    </div>
  );
}

export function ShoppingProgress({ workflow = null, isSubmitting = false }) {
  const activeIdx = deriveStageIndex(workflow, isSubmitting);
  const status = workflow?.status;
  const isRunning = isSubmitting || status === "RUNNING" || status === "PENDING";
  const isError =
    status === "FAILED" ||
    status === "BLOCKED_BY_SECURITY" ||
    status === "NOT_CONFIGURED";
  const isDone = status === "COMPLETED" || status === "APPROVED";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-text-primary">Order Progress</span>
        {workflow ? (
          <ShoppingStatusBadge status={workflow.status} />
        ) : isSubmitting ? (
          <Badge tone="purple" dot pulse>
            Searching
          </Badge>
        ) : (
          <Badge tone="slate">Ready</Badge>
        )}
      </div>

      <div className="space-y-2">
        {STAGE_SEQUENCE.map((stage, index) => {
          const Icon = stage.icon;
          const completed =
            isDone ||
            (activeIdx > index && !isError) ||
            (status === "AWAITING_USER_APPROVAL" && index < 3);
          const current = !isDone && activeIdx === index;

          return (
            <div
              key={stage.key}
              className={`flex items-center gap-2.5 rounded-lg border px-3 py-2 text-xs transition-colors ${
                current && isError
                  ? "border-[#FECDCA] bg-[#FEF3F2] text-[#B42318] dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200"
                  : current
                    ? "border-[#ABEFC6] bg-[#ECFDF3] text-[#067647] dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200"
                    : completed
                      ? "border-border-subtle bg-bg-primary text-text-primary"
                      : "border-border-subtle bg-bg-card text-text-muted"
              }`}
            >
              <span className="shrink-0">
                {current && isRunning ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-[#16A36A]" />
                ) : current && isError ? (
                  <AlertTriangle className="h-3.5 w-3.5 text-[#D92D20]" />
                ) : completed ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-[#12B76A]" />
                ) : current ? (
                  <Clock className="h-3.5 w-3.5 text-[#16A36A]" />
                ) : (
                  <Icon className="h-3.5 w-3.5 text-text-muted" />
                )}
              </span>
              <span className="font-medium truncate">{stage.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

