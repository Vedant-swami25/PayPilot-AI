import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { GitCompare, RefreshCw, Search, Trash2 } from "lucide-react";
import { PageContainer } from "@/components/layout/MainLayout";
import { PageTransition } from "@/components/animations/PageTransition";
import { ProductComparison as ComparisonTable } from "@/components/commerce/ProductComparison";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { EmptyState, Skeleton } from "@/components/ui/Skeleton";
import { useCommerce, useWorkflow } from "@/hooks/useCommerce";
import { productService } from "@/services/productService";
import { useAppStore } from "@/store/useAppStore";

export default function ProductComparison() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const workflowId = searchParams.get("workflowId");
  const { compareIds, clearCompareProducts } = useCommerce();
  const aiPreferences = useAppStore((s) => s.aiPreferences);

  const { data: workflow } = useWorkflow(workflowId);

  const [budget, setBudget] = useState("");
  const [currency, setCurrency] = useState(aiPreferences?.preferredCurrency || "USD");

  const compareMutation = useMutation({
    mutationFn: (payload) => productService.compareProducts(payload),
  });

  useEffect(() => {
    if (compareIds.length >= 2) {
      compareMutation.mutate({
        productIds: compareIds,
        budget: budget ? Number(budget) : null,
        currency,
        requirements: [],
      });
    }
    // Only re-run when compareIds or currency changes explicitly via UI triggers below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compareIds.join(","), currency]);

  const activeComparison =
    workflow?.comparison_result && compareIds.length < 2
      ? workflow.comparison_result
      : compareMutation.data;

  const handleRecalculate = (e) => {
    e.preventDefault();
    if (compareIds.length < 2) return;
    compareMutation.mutate({
      productIds: compareIds,
      budget: budget ? Number(budget) : null,
      currency,
      requirements: [],
    });
  };

  return (
    <PageTransition>
      <PageContainer
        title="Compare Products"
        subtitle="Side-by-side product cards, price comparisons, and specification matrix."
        action={
          <div className="flex items-center gap-2">
            {compareIds.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                icon={<Trash2 className="h-4 w-4" />}
                onClick={clearCompareProducts}
              >
                Clear Selection ({compareIds.length})
              </Button>
            )}
            <Link to="/products">
              <Button variant="secondary" size="sm" icon={<Search className="h-4 w-4" />}>
                Add Products
              </Button>
            </Link>
          </div>
        }
      >
        <div className="space-y-5">
          {compareIds.length >= 2 && (
            <Card padding="p-4">
              <form
                onSubmit={handleRecalculate}
                className="flex flex-wrap items-end gap-3"
              >
                <div>
                  <label
                    htmlFor="compare-budget"
                    className="block text-[11px] font-medium text-text-secondary mb-1"
                  >
                    Target Budget Cap ({currency})
                  </label>
                  <input
                    id="compare-budget"
                    type="number"
                    min="1"
                    step="0.01"
                    value={budget}
                    onChange={(e) => setBudget(e.target.value)}
                    placeholder="Optional max budget"
                    className="rounded-xl border border-border-subtle bg-bg-secondary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30 focus:border-[#16A36A]"
                  />
                </div>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  loading={compareMutation.isPending}
                  icon={<RefreshCw className="h-3.5 w-3.5" />}
                >
                  Re-Evaluate Budget Match
                </Button>
              </form>
            </Card>
          )}

          {compareMutation.isError && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 dark:border-rose-500/35 dark:bg-rose-500/10 p-4 text-xs text-[#B42318] dark:text-rose-300">
              {compareMutation.error?.message ||
                "Unable to compute product comparison."}
            </div>
          )}

          {compareMutation.isPending ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Skeleton className="h-24" />
                <Skeleton className="h-24" />
                <Skeleton className="h-24" />
                <Skeleton className="h-24" />
              </div>
              <Skeleton className="h-80 w-full" />
            </div>
          ) : !activeComparison ? (
            <EmptyState
              icon={<GitCompare className="h-5 w-5" />}
              title="Select at least 2 products to compare"
              description="Toggle 'Compare' on products in Discover or start a shopping search to compare options side by side."
              action={
                <div className="flex flex-wrap justify-center gap-2">
                  <Link to="/products">
                    <Button variant="primary" size="sm">
                      Browse Products
                    </Button>
                  </Link>
                  <Link to="/command-center">
                    <Button variant="outline" size="sm">
                      Open Shopping Assistant
                    </Button>
                  </Link>
                </div>
              }
            />
          ) : (
            <ComparisonTable
              comparison={activeComparison}
              onSelectProduct={(item) =>
                navigate(
                  `/checkout?productId=${encodeURIComponent(item.product_id)}${
                    workflowId ? `&workflowId=${encodeURIComponent(workflowId)}` : ""
                  }&currency=${encodeURIComponent(
                    activeComparison?.currency || currency || "USD"
                  )}`
                )
              }
            />
          )}
        </div>
      </PageContainer>
    </PageTransition>
  );
}
