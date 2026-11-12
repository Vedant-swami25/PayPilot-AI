import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AlertCircle, GitCompare, Search, ShoppingBag } from "lucide-react";
import { PageContainer } from "@/components/layout/MainLayout";
import { PageTransition } from "@/components/animations/PageTransition";
import { SearchBar, FilterPanel } from "@/components/commerce/SearchFilters";
import { ProductGrid } from "@/components/commerce/ProductCard";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { CardSkeleton, EmptyState } from "@/components/ui/Skeleton";
import { useCommerce, useProductSearch } from "@/hooks/useCommerce";
import { useAppStore } from "@/store/useAppStore";

const DISCOVERY_PRESETS = [
  "Laptop for AI development",
  "Noise cancelling headphones",
  "Mechanical keyboard",
  "4K Thunderbolt monitor",
];

export default function ProductDiscovery() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const paramQuery = searchParams.get("query") || "";
  const aiPreferences = useAppStore((s) => s.aiPreferences);
  const { compareIds, toggleCompareProduct, clearCompareProducts } = useCommerce();

  const [queryInput, setQueryInput] = useState(paramQuery);
  const [submittedQuery, setSubmittedQuery] = useState(paramQuery);
  const [maxPrice, setMaxPrice] = useState("");
  const [currency, setCurrency] = useState(aiPreferences?.preferredCurrency || "USD");
  const [category, setCategory] = useState("ALL");
  const [sortBy, setSortBy] = useState("relevance");

  useEffect(() => {
    if (paramQuery && paramQuery !== submittedQuery) {
      setQueryInput(paramQuery);
      setSubmittedQuery(paramQuery);
    }
  }, [paramQuery, submittedQuery]);

  const { data, isFetching, error } = useProductSearch(
    {
      query: submittedQuery,
      maxPrice: maxPrice || null,
      currency,
      limit: 18,
    },
    { enabled: Boolean(submittedQuery) }
  );

  const categories = useMemo(() => {
    const raw = (data?.products || [])
      .map((p) => p.category)
      .filter(Boolean);
    return Array.from(new Set(raw)).sort();
  }, [data]);

  const displayedProducts = useMemo(() => {
    let list = [...(data?.products || [])];
    if (category !== "ALL") {
      list = list.filter((p) => p.category === category);
    }
    if (sortBy === "price_asc") {
      list.sort(
        (a, b) =>
          Number(a.display_price ?? a.price ?? 0) -
          Number(b.display_price ?? b.price ?? 0)
      );
    } else if (sortBy === "price_desc") {
      list.sort(
        (a, b) =>
          Number(b.display_price ?? b.price ?? 0) -
          Number(a.display_price ?? a.price ?? 0)
      );
    }
    return list;
  }, [data, category, sortBy]);

  const handleSearch = (customQuery = null) => {
    const q = (customQuery ?? queryInput).trim();
    if (!q) return;
    if (customQuery) setQueryInput(customQuery);
    setCategory("ALL");
    setSubmittedQuery(q);
    setSearchParams({ query: q });
  };

  const handleResetFilters = () => {
    setMaxPrice("");
    setCurrency("USD");
    setCategory("ALL");
    setSortBy("relevance");
  };

  const providerUnavailable =
    data?.provider_status === "NOT_CONFIGURED" ||
    data?.provider_status === "UNAVAILABLE";
  const hiddenByFrontendFilters =
    Boolean(data?.products?.length) && displayedProducts.length === 0;

  return (
    <PageTransition>
      <PageContainer
        title="Discover Products"
        subtitle="Search live merchant inventory, inspect verified specs, and add products to compare or purchase."
        action={
          <div className="flex items-center gap-2">
            {compareIds.length > 0 && (
              <>
                <Button variant="ghost" size="sm" onClick={clearCompareProducts}>
                  Clear ({compareIds.length})
                </Button>
                <Link to="/compare">
                  <Button
                    variant="emerald"
                    size="sm"
                    icon={<GitCompare className="h-4 w-4" />}
                  >
                    Compare Selected ({compareIds.length})
                  </Button>
                </Link>
              </>
            )}
          </div>
        }
      >
        <div className="space-y-5">
          <Card className="space-y-4">
            <SearchBar
              value={queryInput}
              onChange={setQueryInput}
              onSubmit={() => handleSearch()}
              loading={isFetching}
            />

            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-medium text-text-muted">
                Popular categories:
              </span>
              {DISCOVERY_PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => handleSearch(preset)}
                  className="rounded-lg border border-border-subtle bg-bg-secondary px-2.5 py-1 text-xs text-text-secondary hover:border-[#16A36A]/50 hover:text-text-primary transition-colors"
                >
                  {preset}
                </button>
              ))}
            </div>
          </Card>

          <FilterPanel
            maxPrice={maxPrice}
            onMaxPriceChange={setMaxPrice}
            currency={currency}
            onCurrencyChange={setCurrency}
            category={category}
            onCategoryChange={setCategory}
            sortBy={sortBy}
            onSortByChange={setSortBy}
            categories={categories}
            onReset={handleResetFilters}
          />

          {/* Provider diagnostics banner ONLY for unavailable / not-configured / test-data / non-empty notices */}
          {!error && data && (providerUnavailable || data.is_test_data) && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10 p-3.5 text-xs text-amber-800 dark:text-amber-200 flex items-start justify-between gap-3">
              <div className="flex items-start gap-2.5">
                <AlertCircle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
                <div>
                  <p className="font-semibold">
                    {data.provider_status === "NOT_CONFIGURED"
                      ? `Product provider (${data.provider || "catalog"}) is not configured`
                      : data.provider_status === "UNAVAILABLE"
                        ? `Product provider (${data.provider || "catalog"}) is temporarily unavailable`
                        : `Provider: ${data.provider || "Unknown"}`}
                  </p>
                  {data.message && <p className="mt-0.5 opacity-90">{data.message}</p>}
                </div>
              </div>
              {data.is_test_data && <Badge tone="amber">TEST DATA</Badge>}
            </div>
          )}

          {!error && data && displayedProducts.length > 0 && data.exchange_rate && data.display_currency && data.products?.some((p) => (p.original_currency || p.currency) !== data.display_currency) && (
            <div className="rounded-xl border border-border-subtle bg-bg-secondary px-3.5 py-2.5 text-xs text-text-secondary flex flex-wrap items-center justify-between gap-2">
              <span>
                Displaying live converted prices in{" "}
                <strong className="text-text-primary">{data.display_currency}</strong>{" "}
                (1 {data.products[0].original_currency || "USD"} = {Number(data.exchange_rate).toFixed(2)} {data.display_currency}).
                Original merchant prices remain preserved for checkout verification.
              </span>
            </div>
          )}

          {!error && data && displayedProducts.length > 0 && data.message && !data.is_test_data && !providerUnavailable && (
            <div className="rounded-xl border border-border-subtle bg-bg-secondary p-3.5 text-xs text-text-secondary flex items-start gap-2.5">
              <AlertCircle className="h-4 w-4 shrink-0 text-text-muted mt-0.5" />
              <p>{data.message}</p>
            </div>
          )}

          {error && (
            <div
              role="alert"
              className="rounded-xl border border-rose-200 bg-rose-50 dark:border-rose-500/35 dark:bg-rose-500/10 p-4 text-xs text-[#B42318] dark:text-rose-300 flex items-start gap-2.5"
            >
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Unable to complete product search</p>
                <p className="mt-0.5">
                  {error.message || "The product search service returned an error. Please try again."}
                </p>
              </div>
            </div>
          )}

          {/* Results Area */}
          {isFetching ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
              <CardSkeleton />
              <CardSkeleton />
              <CardSkeleton />
            </div>
          ) : error ? null : !submittedQuery ? (
            <EmptyState
              icon={<Search className="h-5 w-5" />}
              title="Search the live commerce catalog"
              description="Enter a product query above or pick a popular search to inspect verified pricing, availability, and merchant details."
              action={
                <Link to="/command-center">
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<ShoppingBag className="h-4 w-4" />}
                  >
                    Open Shopping Assistant
                  </Button>
                </Link>
              }
            />
          ) : hiddenByFrontendFilters ? (
            <EmptyState
              icon={<Search className="h-5 w-5" />}
              title="No products match the active category filter"
              description={`${data.products.length} product(s) were returned for "${submittedQuery}", but none match the selected filters.`}
              action={
                <Button variant="primary" size="sm" onClick={handleResetFilters}>
                  Reset Filters
                </Button>
              }
            />
          ) : displayedProducts.length === 0 ? (
            <EmptyState
              icon={<Search className="h-5 w-5" />}
              title={
                providerUnavailable
                  ? "Product catalog unavailable"
                  : `No products found for "${submittedQuery}"`
              }
              description={
                providerUnavailable
                  ? data?.message || "The external catalog provider is currently unavailable."
                  : data?.message ||
                    "Try broader keywords, remove the budget cap, or search in natural language using the Shopping Assistant."
              }
              action={
                maxPrice ? (
                  <Button variant="secondary" size="sm" onClick={handleResetFilters}>
                    Reset Filters
                  </Button>
                ) : null
              }
            />
          ) : (
            <ProductGrid
              products={displayedProducts}
              compareIds={compareIds}
              onToggleCompare={toggleCompareProduct}
              onSelectForCheckout={(product) =>
                navigate(
                  `/checkout?productId=${encodeURIComponent(product.id)}&currency=${encodeURIComponent(
                    product.display_currency || currency || "USD"
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
