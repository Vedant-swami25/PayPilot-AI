import React from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, CreditCard } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { PaymentStatusBadge } from "@/components/payments/PaymentStatus";
import { formatCurrency } from "@/utils/formatCurrency";
import { formatDateTime } from "@/utils/formatDate";

export function TransactionCard({ transaction }) {
  if (!transaction) return null;

  return (
    <Link to={`/transactions/${transaction.id}`} className="block group">
      <Card
        hover
        padding="p-4"
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-4"
      >
        <div className="flex items-start sm:items-center gap-3.5 min-w-0">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 dark:bg-white/10 border border-border-subtle text-[#101828] dark:text-slate-200">
            <CreditCard className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-text-primary font-mono truncate">
                {transaction.paypal_capture_id || transaction.order_id}
              </span>
              <PaymentStatusBadge status={transaction.status} />
            </div>
            <p className="text-xs text-text-secondary mt-1">
              {transaction.payment_method || "PayPal"} •{" "}
              {formatDateTime(transaction.created_at)}
            </p>
            {transaction.failure_reason && (
              <p className="text-xs text-[#D92D20] mt-1 truncate">
                {transaction.failure_reason}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0">
          <div className="text-left sm:text-right">
            <p className="text-base font-mono font-bold text-text-primary tabular-nums">
              {formatCurrency(transaction.amount, transaction.currency)}
            </p>
            <p className="text-[11px] text-text-secondary">
              {transaction.currency}
            </p>
          </div>
          <ArrowUpRight className="h-4 w-4 text-text-muted group-hover:text-text-primary transition-colors" />
        </div>
      </Card>
    </Link>
  );
}
