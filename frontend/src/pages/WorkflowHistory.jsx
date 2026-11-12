import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, CreditCard, History, Search, ShoppingBag } from "lucide-react";
import { PageContainer } from "@/components/layout/MainLayout";
import { PageTransition } from "@/components/animations/PageTransition";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, Skeleton } from "@/components/ui/Skeleton";
import { ShoppingStatusBadge } from "@/components/commerce/ShoppingStatus";
import { useCommerceHistory } from "@/hooks/useCommerce";
import { formatCurrency } from "@/utils/formatCurrency";
import { formatDateTime } from "@/utils/formatDate";

export default function WorkflowHistory() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const { data, isLoading } = useCommerceHistory({ limit: 50 });

  const filtered = useMemo(() => {
    const list = data?.workflows || [];
    return list.filter((wf) => {
      if (statusFilter !== "ALL" && wf.status !== statusFilter) return false;
      if (search.trim()) {
        const q = search.trim().toLowerCase();
        return (
          wf.request_text?.toLowerCase().includes(q) ||
          wf.recommendation?.recommended_product_name?.toLowerCase().includes(q) ||
          wf.id?.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [data, search, statusFilter]);

  return (
    <PageTransition>
      <PageContainer
        title="Shopping History"
        subtitle="Review your past searches, product picks, and PayPal checkout sessions."
        action={
          <Link to="/command-center">
            <Button variant="primary" size="md" icon={<ShoppingBag className="h-4 w-4" />}>
              New Search
            </Button>
          </Link>
        }
      >
        <div className="space-y-5">
          {/* Filter Controls */}
          <Card padding="p-4" className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter by search query, product name, or session ID..."
                className="w-full rounded-xl border border-border-subtle bg-bg-secondary pl-9 pr-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30 focus:border-[#16A36A]"
              />
            </div>
            <select
              aria-label="Filter shopping session status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-xl border border-border-subtle bg-bg-secondary px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30"
            >
              <option value="ALL">All Statuses</option>
              <option value="AWAITING_USER_APPROVAL">Ready for Review</option>
              <option value="ORDER_CREATED">Checkout Ready</option>
              <option value="COMPLETED">Completed</option>
              <option value="BLOCKED_BY_SECURITY">Blocked by Limit</option>
              <option value="FAILED">Unavailable</option>
              <option value="CANCELLED">Cancelled</option>
            </select>
          </Card>

          {isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<History className="h-5 w-5" />}
              title="No matching shopping sessions"
              description="Adjust your search filter or start a new search in the Shopping Assistant."
              action={
                <Link to="/command-center">
                  <Button variant="primary" size="sm">
                    Open Shopping Assistant
                  </Button>
                </Link>
              }
            />
          ) : (
            <div className="space-y-3">
              {filtered.map((wf) => (
                <Card key={wf.id} hover padding="p-4" className="space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="space-y-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <ShoppingStatusBadge
                          status={wf.status}
                          currentStep={wf.current_step}
                        />
                        <span className="text-[11px] font-mono text-text-muted">
                          {wf.id.slice(0, 8)}...
                        </span>
                        <span className="text-xs text-text-secondary">
                          {formatDateTime(wf.created_at)}
                        </span>
                      </div>
                      <h3 className="text-sm font-semibold text-text-primary">
                        {wf.request_text}
                      </h3>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 shrink-0">
                      {wf.order_id && (
                        <Link
                          to={`/checkout?paymentId=${encodeURIComponent(
                            wf.order_id
                          )}&workflowId=${encodeURIComponent(wf.id)}`}
                        >
                          <Button
                            variant="outline"
                            size="xs"
                            icon={<CreditCard className="h-3.5 w-3.5" />}
                          >
                            Checkout
                          </Button>
                        </Link>
                      )}
                      <Link
                        to={`/command-center?workflowId=${encodeURIComponent(
                          wf.id
                        )}`}
                      >
                        <Button
                          variant="secondary"
                          size="xs"
                          icon={<ArrowRight className="h-3.5 w-3.5" />}
                        >
                          Open
                        </Button>
                      </Link>
                    </div>
                  </div>

                  {(wf.recommendation || wf.parsed_intent?.budget) && (
                    <div className="flex flex-wrap items-center gap-2 border-t border-border-subtle pt-2.5 text-xs">
                      {wf.recommendation?.recommended_product_name && (
                        <Badge tone="slate">
                          Top Pick: {wf.recommendation.recommended_product_name}
                        </Badge>
                      )}
                      {wf.recommendation?.recommended_price != null && (
                        <Badge tone="emerald">
                          {formatCurrency(
                            wf.recommendation.recommended_price,
                            wf.recommendation.currency
                          )}
                        </Badge>
                      )}
                      {wf.discovered_products?.length > 0 && (
                        <span className="text-text-secondary">
                          {wf.discovered_products.length} products analyzed
                        </span>
                      )}
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}
        </div>
      </PageContainer>
    </PageTransition>
  );
}
