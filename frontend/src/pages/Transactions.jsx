import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, CreditCard, Download, Search, Wallet } from "lucide-react";
import { PageContainer } from "@/components/layout/MainLayout";
import { PageTransition } from "@/components/animations/PageTransition";
import { TransactionCard } from "@/components/payments/TransactionCard";
import { PaymentStatusBadge } from "@/components/payments/PaymentStatus";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, Skeleton } from "@/components/ui/Skeleton";
import { useTransactions, useTransactionSummary } from "@/hooks/usePayments";
import { formatCurrency } from "@/utils/formatCurrency";
import { formatDateTime } from "@/utils/formatDate";

export default function Transactions() {
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [search, setSearch] = useState("");

  const { data: txData, isLoading } = useTransactions({
    status: statusFilter === "ALL" ? null : statusFilter,
    limit: 50,
  });
  const { data: summary } = useTransactionSummary();

  const filtered = useMemo(() => {
    const items = txData?.transactions || [];
    if (!search.trim()) return items;
    const q = search.trim().toLowerCase();
    return items.filter(
      (tx) =>
        tx.id?.toLowerCase().includes(q) ||
        tx.order_id?.toLowerCase().includes(q) ||
        tx.paypal_capture_id?.toLowerCase().includes(q) ||
        tx.payment_method?.toLowerCase().includes(q) ||
        tx.failure_reason?.toLowerCase().includes(q)
    );
  }, [txData, search]);

  const handleExportCsv = () => {
    if (!filtered.length) return;
    const header = [
      "transaction_id",
      "order_id",
      "paypal_capture_id",
      "amount",
      "currency",
      "status",
      "payment_method",
      "created_at",
    ];
    const rows = filtered.map((tx) =>
      [
        tx.id,
        tx.order_id,
        tx.paypal_capture_id || "",
        tx.amount,
        tx.currency,
        tx.status,
        tx.payment_method || "",
        tx.created_at,
      ]
        .map((v) => `"${String(v ?? "").replaceAll('"', '""')}"`)
        .join(",")
    );
    const csv = [header.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "paypilot-transactions.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const spendEntries = Object.entries(summary?.total_spent_by_currency || {});

  return (
    <PageTransition>
      <PageContainer
        title="Transaction Ledger"
        subtitle="Audit all user-authorized PayPal captures, pending orders, and refunds."
        action={
          <Button
            variant="secondary"
            size="sm"
            disabled={!filtered.length}
            icon={<Download className="h-4 w-4" />}
            onClick={handleExportCsv}
          >
            Export CSV
          </Button>
        }
      >
        <div className="space-y-6">
          {/* Summary Stats */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <p className="text-xs font-medium text-text-secondary">Total Transactions</p>
              <p className="mt-1.5 text-2xl font-mono font-bold text-text-primary tabular-nums">
                {summary?.total_count ?? 0}
              </p>
            </Card>
            <Card>
              <p className="text-xs font-medium text-text-secondary">Completed Captures</p>
              <p className="mt-1.5 text-2xl font-mono font-bold text-[#12B76A] tabular-nums">
                {summary?.completed_count ?? 0}
              </p>
            </Card>
            <Card>
              <p className="text-xs font-medium text-text-secondary">Pending Approval</p>
              <p className="mt-1.5 text-2xl font-mono font-bold text-amber-600 dark:text-amber-400 tabular-nums">
                {summary?.pending_count ?? 0}
              </p>
            </Card>
            <Card>
              <p className="text-xs font-medium text-text-secondary">Failed / Refunded</p>
              <p className="mt-1.5 text-2xl font-mono font-bold text-[#D92D20] tabular-nums">
                {(summary?.failed_count ?? 0) + (summary?.refunded_count ?? 0)}
              </p>
            </Card>
          </div>

          {spendEntries.length > 0 && (
            <Card padding="p-4" className="flex flex-wrap items-center gap-3">
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-text-secondary">
                <Wallet className="h-4 w-4 text-[#16A36A]" />
                Settled Spend Totals:
              </span>
              {spendEntries.map(([cur, total]) => (
                <Badge key={cur} tone="emerald">
                  {formatCurrency(total, cur)} ({cur})
                </Badge>
              ))}
            </Card>
          )}

          {/* Filter & Search Bar */}
          <Card padding="p-4" className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by Capture ID, Order ID, or method..."
                className="w-full rounded-xl border border-border-subtle bg-bg-secondary pl-9 pr-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30 focus:border-[#16A36A]"
              />
            </div>

            <select
              aria-label="Filter transaction status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-xl border border-border-subtle bg-bg-secondary px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30"
            >
              <option value="ALL">All Statuses</option>
              <option value="COMPLETED">Completed</option>
              <option value="PENDING_APPROVAL">Pending Approval</option>
              <option value="APPROVED">Approved</option>
              <option value="FAILED">Failed</option>
              <option value="CANCELLED">Cancelled</option>
              <option value="REFUNDED">Refunded</option>
            </select>
          </Card>

          {/* Ledger Table (Desktop) + Cards (Mobile) */}
          {isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<CreditCard className="h-5 w-5" />}
              title="No matching transactions"
              description="Authorized PayPal transactions and captures will appear here."
            />
          ) : (
            <>
              <Card padding="p-0" className="hidden md:block overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead>
                      <tr className="border-b border-border-subtle bg-bg-secondary text-text-secondary">
                        <th className="py-3 px-4 font-semibold">Reference / Capture ID</th>
                        <th className="py-3 px-4 font-semibold">Order ID</th>
                        <th className="py-3 px-4 font-semibold">Method</th>
                        <th className="py-3 px-4 font-semibold">Date</th>
                        <th className="py-3 px-4 font-semibold">Status</th>
                        <th className="py-3 px-4 font-semibold text-right">Amount</th>
                        <th className="py-3 px-4 font-semibold text-right">Receipt</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-subtle">
                      {filtered.map((tx) => (
                        <tr
                          key={tx.id}
                          className="hover:bg-slate-50 dark:hover:bg-white/[0.02] transition-colors"
                        >
                          <td className="py-3.5 px-4 font-mono font-medium text-text-primary">
                            {tx.paypal_capture_id || tx.id}
                          </td>
                          <td className="py-3.5 px-4 font-mono text-text-secondary truncate max-w-[160px]">
                            {tx.order_id}
                          </td>
                          <td className="py-3.5 px-4 text-text-primary">
                            {tx.payment_method || "PayPal"}
                          </td>
                          <td className="py-3.5 px-4 text-text-secondary whitespace-nowrap">
                            {formatDateTime(tx.created_at)}
                          </td>
                          <td className="py-3.5 px-4">
                            <PaymentStatusBadge status={tx.status} />
                          </td>
                          <td className="py-3.5 px-4 text-right font-mono font-semibold text-text-primary tabular-nums whitespace-nowrap">
                            {formatCurrency(tx.amount, tx.currency)}
                          </td>
                          <td className="py-3.5 px-4 text-right">
                            <Link
                              to={`/transactions/${tx.id}`}
                              className="inline-flex items-center gap-1 font-semibold text-[#16A36A] hover:underline"
                            >
                              View <ArrowUpRight className="h-3.5 w-3.5" />
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              <div className="md:hidden space-y-3">
                {filtered.map((tx) => (
                  <TransactionCard key={tx.id} transaction={tx} />
                ))}
              </div>
            </>
          )}
        </div>
      </PageContainer>
    </PageTransition>
  );
}
