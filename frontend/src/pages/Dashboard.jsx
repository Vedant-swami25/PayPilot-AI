import React, { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  CreditCard,
  Search,
  ShieldCheck,
  ShoppingBag,
  TrendingUp,
  Wallet,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PageContainer } from "@/components/layout/MainLayout";
import { PageTransition } from "@/components/animations/PageTransition";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, Skeleton } from "@/components/ui/Skeleton";
import { ProductCard } from "@/components/commerce/ProductCard";
import { ShoppingStatusBadge } from "@/components/commerce/ShoppingStatus";
import { TransactionCard } from "@/components/payments/TransactionCard";
import { useAuth } from "@/hooks/useAuth";
import {
  useCommerce,
  useCommerceHistory,
  useSubmitCommerceRequest,
  useWorkflow,
} from "@/hooks/useCommerce";
import { useTransactionSummary } from "@/hooks/usePayments";
import { useAppStore } from "@/store/useAppStore";
import { SUGGESTED_PROMPTS } from "@/utils/constants";
import { formatCurrency } from "@/utils/formatCurrency";
import { formatDate, formatRelativeTime } from "@/utils/formatDate";

export default function Dashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const activeWorkflowId = useAppStore((s) => s.activeWorkflowId);
  const aiPreferences = useAppStore((s) => s.aiPreferences);
  const { compareIds, toggleCompareProduct } = useCommerce();

  const [commandText, setCommandText] = useState("");

  const { data: activeWorkflow } = useWorkflow(activeWorkflowId);
  const { data: historyData, isLoading: historyLoading } = useCommerceHistory({
    limit: 6,
  });
  const { data: summaryData, isLoading: summaryLoading } = useTransactionSummary();

  const submitRequest = useSubmitCommerceRequest();

  const spendingLimit = user?.spending_limit;
  const preferredCurrency =
    spendingLimit?.currency || aiPreferences?.preferredCurrency || "USD";

  const spendByCurrency = summaryData?.total_spent_by_currency || {};
  const primarySpent =
    spendByCurrency[preferredCurrency] ??
    Object.values(spendByCurrency)[0] ??
    0;
  const primarySpentCurrency =
    spendByCurrency[preferredCurrency] != null
      ? preferredCurrency
      : Object.keys(spendByCurrency)[0] || preferredCurrency;

  const chartData = useMemo(() => {
    const txs = summaryData?.recent_transactions || [];
    if (!txs.length) return [];
    return [...txs]
      .reverse()
      .map((tx) => ({
        date: formatDate(tx.created_at),
        amount: Number(tx.amount || 0),
        status: tx.status,
      }));
  }, [summaryData]);

  // Real recommended products derived strictly from active/recent backend shopping sessions
  const recommendedProducts = useMemo(() => {
    const seen = new Set();
    const collected = [];
    const pool = [
      ...(activeWorkflow?.discovered_products || []),
      ...(historyData?.workflows || []).flatMap((w) => w.discovered_products || []),
    ];
    for (const item of pool) {
      if (!item?.id || seen.has(item.id)) continue;
      seen.add(item.id);
      collected.push(item);
      if (collected.length >= 3) break;
    }
    return collected;
  }, [activeWorkflow, historyData]);

  const handleCommandSubmit = async (e) => {
    e.preventDefault();
    const cleaned = commandText.trim();
    if (!cleaned || submitRequest.isPending) return;
    try {
      const wf = await submitRequest.mutateAsync({
        requestText: cleaned,
        currency: preferredCurrency,
        quantity: 1,
      });
      setCommandText("");
      navigate(`/command-center?workflowId=${wf.id}`);
    } catch {
      // Handled via mutation toast
    }
  };

  return (
    <PageTransition>
      <PageContainer
        title={`Welcome back, ${user?.name?.split(" ")[0] || "there"}`}
        subtitle="Discover products across merchants, compare prices, and manage verified PayPal payments."
        action={
          <Link to="/products">
            <Button variant="primary" size="md" icon={<Search className="h-4 w-4" />}>
              Browse Products
            </Button>
          </Link>
        }
      >
        <div className="space-y-6">
          {/* Natural-Language Shopping Search Bar */}
          <Card className="p-5 sm:p-6">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#101828] dark:bg-white/10 text-white shrink-0">
                  <Search className="h-4 w-4 text-[#16A36A]" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-text-primary">
                    What are you looking to buy?
                  </h2>
                  <p className="text-xs text-text-secondary">
                    Describe a product and target budget — PayPilot searches live merchant listings and compares deals.
                  </p>
                </div>
              </div>
              <Badge tone="emerald" dot>
                Currency: {preferredCurrency}
              </Badge>
            </div>

            <form
              onSubmit={handleCommandSubmit}
              className="flex flex-col sm:flex-row gap-2.5"
            >
              <input
                type="text"
                value={commandText}
                onChange={(e) => setCommandText(e.target.value)}
                placeholder="e.g. Find wireless noise-cancelling headphones under $250 USD..."
                className="flex-1 rounded-xl border border-border-subtle bg-bg-secondary px-4 py-3 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30 focus:border-[#16A36A]"
              />
              <Button
                type="submit"
                variant="emerald"
                size="lg"
                loading={submitRequest.isPending}
                disabled={!commandText.trim()}
                icon={<ArrowRight className="h-4 w-4" />}
              >
                Find Products
              </Button>
            </form>

            <div className="mt-3.5 flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-medium text-text-muted">
                Popular searches:
              </span>
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => setCommandText(prompt)}
                  className="rounded-lg border border-border-subtle bg-bg-secondary px-2.5 py-1 text-[11px] text-text-secondary hover:border-[#16A36A]/50 hover:text-text-primary transition-colors text-left"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </Card>

          {/* Summary KPI Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <Card>
              <div className="flex items-center justify-between text-xs font-medium text-text-secondary">
                <span>Monthly / Total Spend</span>
                <Wallet className="h-4 w-4 text-[#16A36A]" />
              </div>
              {summaryLoading ? (
                <Skeleton className="h-8 w-28 mt-2" />
              ) : (
                <p className="mt-2 text-2xl font-mono font-bold text-text-primary tabular-nums">
                  {formatCurrency(primarySpent, primarySpentCurrency)}
                </p>
              )}
              <p className="mt-1 text-[11px] text-text-muted">
                Across {summaryData?.completed_count ?? 0} completed orders
              </p>
            </Card>

            <Card>
              <div className="flex items-center justify-between text-xs font-medium text-text-secondary">
                <span>Shopping Activity</span>
                <ShoppingBag className="h-4 w-4 text-[#101828] dark:text-slate-300" />
              </div>
              {historyLoading ? (
                <Skeleton className="h-8 w-20 mt-2" />
              ) : (
                <p className="mt-2 text-2xl font-mono font-bold text-text-primary tabular-nums">
                  {historyData?.total ?? 0}
                </p>
              )}
              <p className="mt-1 text-[11px] text-text-muted">
                Saved comparisons & picks
              </p>
            </Card>

            <Card>
              <div className="flex items-center justify-between text-xs font-medium text-text-secondary">
                <span>PayPal Orders</span>
                <CreditCard className="h-4 w-4 text-[#16A36A]" />
              </div>
              {summaryLoading ? (
                <Skeleton className="h-8 w-20 mt-2" />
              ) : (
                <p className="mt-2 text-2xl font-mono font-bold text-text-primary tabular-nums">
                  {summaryData?.total_count ?? 0}
                </p>
              )}
              <p className="mt-1 text-[11px] text-text-muted">
                {summaryData?.pending_count ?? 0} pending •{" "}
                {summaryData?.failed_count ?? 0} failed
              </p>
            </Card>

            <Card>
              <div className="flex items-center justify-between text-xs font-medium text-text-secondary">
                <span>Per-Order Limit</span>
                <ShieldCheck className="h-4 w-4 text-[#16A36A]" />
              </div>
              <p className="mt-2 text-2xl font-mono font-bold text-text-primary tabular-nums">
                {spendingLimit?.max_single_transaction != null
                  ? formatCurrency(
                      spendingLimit.max_single_transaction,
                      spendingLimit.currency || preferredCurrency
                    )
                  : "Unlimited"}
              </p>
              <p className="mt-1 text-[11px] text-text-muted">
                Confirmation:{" "}
                {spendingLimit?.require_manual_approval !== false
                  ? "Required Before Pay"
                  : "Standard"}
              </p>
            </Card>
          </div>

          {/* Recommended Products from Real Recent Searches */}
          <Card>
            <CardHeader
              title="Recommended Products"
              subtitle="Live merchant matches from your recent shopping searches"
              action={
                <Link
                  to="/products"
                  className="text-xs font-semibold text-[#16A36A] hover:underline inline-flex items-center gap-1"
                >
                  Discover More <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              }
            />
            {historyLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Skeleton className="h-64 w-full" />
                <Skeleton className="h-64 w-full" />
                <Skeleton className="h-64 w-full" />
              </div>
            ) : recommendedProducts.length === 0 ? (
              <EmptyState
                icon={<ShoppingBag className="h-5 w-5" />}
                title="No recommended products yet"
                description="Use the shopping search above or browse Discover to pull live verified product listings."
                action={
                  <Link to="/products">
                    <Button variant="primary" size="sm">
                      Explore Products
                    </Button>
                  </Link>
                }
              />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {recommendedProducts.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    isCompared={compareIds.includes(product.id)}
                    onToggleCompare={toggleCompareProduct}
                    onSelectForCheckout={(prod) =>
                      navigate(`/checkout?productId=${encodeURIComponent(prod.id)}`)
                    }
                  />
                ))}
              </div>
            )}
          </Card>

          {/* Main Analytics & Activity Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left 8 Columns */}
            <div className="lg:col-span-8 space-y-6">
              {/* Monthly Spending Overview Chart */}
              <Card>
                <CardHeader
                  title="Spending Summary"
                  subtitle="Authorized payment activity across recent orders"
                  action={
                    <Link
                      to="/transactions"
                      className="text-xs font-semibold text-[#16A36A] hover:underline inline-flex items-center gap-1"
                    >
                      View All <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  }
                />

                {summaryLoading ? (
                  <Skeleton className="h-56 w-full" />
                ) : chartData.length === 0 ? (
                  <EmptyState
                    icon={<TrendingUp className="h-5 w-5" />}
                    title="No completed payments yet"
                    description="Complete your first PayPal purchase to track spending insights here."
                  />
                ) : (
                  <div className="h-56 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData}>
                        <defs>
                          <linearGradient id="ppSpendGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#16A36A" stopOpacity={0.28} />
                            <stop offset="95%" stopColor="#101828" stopOpacity={0.0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 11, fill: "#667085" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fontSize: 11, fill: "#667085" }}
                          axisLine={false}
                          tickLine={false}
                          width={56}
                        />
                        <RechartsTooltip
                          contentStyle={{
                            backgroundColor: "#101828",
                            borderColor: "#344054",
                            color: "#FFFFFF",
                            borderRadius: "10px",
                            fontSize: "12px",
                          }}
                        />
                        <Area
                          type="monotone"
                          dataKey="amount"
                          stroke="#16A36A"
                          strokeWidth={2}
                          fill="url(#ppSpendGrad)"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </Card>

              {/* Recent Shopping Activity */}
              <Card>
                <CardHeader
                  title="Recent Shopping Activity"
                  subtitle="Resume product review, comparison, or PayPal checkout"
                  action={
                    <Link
                      to="/workflows"
                      className="text-xs font-semibold text-[#16A36A] hover:underline inline-flex items-center gap-1"
                    >
                      All History <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  }
                />

                {historyLoading ? (
                  <div className="space-y-3">
                    <Skeleton className="h-16 w-full" />
                    <Skeleton className="h-16 w-full" />
                  </div>
                ) : !historyData?.workflows?.length ? (
                  <EmptyState
                    icon={<ShoppingBag className="h-5 w-5" />}
                    title="No shopping searches yet"
                    description="Start a search above to discover and compare live merchant products."
                  />
                ) : (
                  <div className="space-y-2.5">
                    {historyData.workflows.map((wf) => (
                      <Link
                        key={wf.id}
                        to={`/command-center?workflowId=${wf.id}`}
                        className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-xl border border-border-subtle bg-bg-secondary p-3.5 hover:border-slate-300 dark:hover:border-slate-600 transition-colors"
                      >
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-text-primary truncate">
                            {wf.request_text}
                          </p>
                          <p className="text-xs text-text-secondary mt-0.5">
                            {formatRelativeTime(wf.created_at)}
                            {wf.recommendation?.recommended_product_name
                              ? ` • Pick: ${wf.recommendation.recommended_product_name}`
                              : ""}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <ShoppingStatusBadge status={wf.status} currentStep={wf.current_step} />
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </Card>

              {/* Recent Transactions */}
              <Card>
                <CardHeader
                  title="Recent Transactions"
                  subtitle="PayPal orders and payment receipts"
                  action={
                    <Link
                      to="/transactions"
                      className="text-xs font-semibold text-[#16A36A] hover:underline inline-flex items-center gap-1"
                    >
                      Full Ledger <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  }
                />
                {summaryLoading ? (
                  <Skeleton className="h-24 w-full" />
                ) : !summaryData?.recent_transactions?.length ? (
                  <EmptyState
                    icon={<CreditCard className="h-5 w-5" />}
                    title="No transactions recorded"
                    description="PayPal orders created and completed through Checkout appear here immediately."
                  />
                ) : (
                  <div className="space-y-2.5">
                    {summaryData.recent_transactions.slice(0, 4).map((tx) => (
                      <TransactionCard key={tx.id} transaction={tx} />
                    ))}
                  </div>
                )}
              </Card>
            </div>

            {/* Right 4 Columns: Current Purchase + Spending Protection */}
            <div className="lg:col-span-4 space-y-6">
              <Card className="space-y-4">
                <CardHeader
                  title="Current Shopping Session"
                  subtitle="Quick resume & checkout status"
                  action={<ShoppingBag className="h-4 w-4 text-[#16A36A]" />}
                />
                {activeWorkflow ? (
                  <div className="space-y-3 rounded-xl border border-border-subtle bg-bg-secondary p-4 text-xs">
                    <p className="text-sm font-medium text-text-primary line-clamp-2">
                      {activeWorkflow.request_text}
                    </p>
                    <div className="flex items-center justify-between gap-2">
                      <ShoppingStatusBadge
                        status={activeWorkflow.status}
                        currentStep={activeWorkflow.current_step}
                        showStage
                      />
                    </div>
                    {activeWorkflow.recommendation?.recommended_product_name && (
                      <div className="rounded-lg border border-border-subtle bg-bg-card p-2.5">
                        <p className="text-[11px] text-text-muted">Top Pick</p>
                        <p className="font-medium text-text-primary truncate mt-0.5">
                          {activeWorkflow.recommendation.recommended_product_name}
                        </p>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-2 pt-1">
                      <Link
                        to={`/command-center?workflowId=${activeWorkflow.id}`}
                        className="flex-1"
                      >
                        <Button variant="primary" size="sm" className="w-full">
                          Open Session
                        </Button>
                      </Link>
                      {activeWorkflow.order_id && (
                        <Link
                          to={`/checkout?paymentId=${encodeURIComponent(
                            activeWorkflow.order_id
                          )}&workflowId=${encodeURIComponent(activeWorkflow.id)}`}
                        >
                          <Button variant="outline" size="sm">
                            Checkout
                          </Button>
                        </Link>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <p className="text-xs text-text-secondary leading-relaxed">
                      Start a natural-language search above or browse live products directly across verified merchants.
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <Link to="/products">
                        <Button variant="secondary" size="sm" className="w-full">
                          Discover
                        </Button>
                      </Link>
                      <Link to="/compare">
                        <Button variant="outline" size="sm" className="w-full">
                          Compare
                        </Button>
                      </Link>
                    </div>
                  </div>
                )}
              </Card>

              <Card className="space-y-4">
                <CardHeader
                  title="Spending Protection"
                  subtitle="Active account guardrails"
                  action={
                    <Link
                      to="/settings"
                      className="text-xs font-semibold text-[#16A36A] hover:underline inline-flex items-center gap-1"
                    >
                      Configure <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  }
                />
                <div className="space-y-2.5 text-xs">
                  <div className="flex items-center justify-between rounded-xl border border-border-subtle bg-bg-secondary px-3 py-2.5">
                    <span className="text-text-secondary">Single-Transaction Cap</span>
                    <span className="font-mono font-semibold text-text-primary tabular-nums">
                      {spendingLimit?.max_single_transaction != null
                        ? formatCurrency(
                            spendingLimit.max_single_transaction,
                            spendingLimit.currency || preferredCurrency
                          )
                        : "Unlimited"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between rounded-xl border border-border-subtle bg-bg-secondary px-3 py-2.5">
                    <span className="text-text-secondary">Daily Cap</span>
                    <span className="font-mono font-semibold text-text-primary tabular-nums">
                      {spendingLimit?.daily_limit != null
                        ? formatCurrency(
                            spendingLimit.daily_limit,
                            spendingLimit.currency || preferredCurrency
                          )
                        : "Unlimited"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between rounded-xl border border-border-subtle bg-bg-secondary px-3 py-2.5">
                    <span className="text-text-secondary">Monthly Cap</span>
                    <span className="font-mono font-semibold text-text-primary tabular-nums">
                      {spendingLimit?.monthly_limit != null
                        ? formatCurrency(
                            spendingLimit.monthly_limit,
                            spendingLimit.currency || preferredCurrency
                          )
                        : "Unlimited"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between rounded-xl border border-emerald-200 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10 px-3 py-2.5">
                    <span className="text-text-secondary">Checkout Gate</span>
                    <Badge tone="emerald" dot>
                      {spendingLimit?.require_manual_approval !== false
                        ? "Manual Confirmation"
                        : "Standard"}
                    </Badge>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </div>
      </PageContainer>
    </PageTransition>
  );
}
