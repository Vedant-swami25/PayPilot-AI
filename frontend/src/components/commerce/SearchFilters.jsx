import React from "react";
import { Filter, Search, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { SUPPORTED_CURRENCIES } from "@/utils/constants";

export function SearchBar({
  value,
  onChange,
  onSubmit,
  loading = false,
  placeholder = "Search products by keyword, brand, or specification...",
}) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit?.();
      }}
      className="flex flex-col sm:flex-row gap-2.5"
    >
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
        <input
          type="search"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-lg border border-border-strong bg-bg-card py-2.5 pl-10 pr-4 text-sm text-text-primary placeholder:text-text-muted focus:border-[#16A36A] focus:outline-none focus:ring-2 focus:ring-[#16A36A]/15"
        />
      </div>
      <Button type="submit" loading={loading} size="md">
        Search Products
      </Button>
    </form>
  );
}

export function FilterPanel({
  maxPrice,
  onMaxPriceChange,
  currency,
  onCurrencyChange,
  category,
  onCategoryChange,
  sortBy,
  onSortByChange,
  categories = [],
  onReset = null,
}) {
  return (
    <div className="rounded-xl border border-border-subtle bg-bg-card p-4 shadow-card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-text-secondary">
          <SlidersHorizontal className="h-3.5 w-3.5 text-[#16A36A]" />
          <span>Filters &amp; Sorting</span>
        </div>
        {onReset && (
          <button
            type="button"
            onClick={onReset}
            className="text-xs font-medium text-[#16A36A] hover:underline"
          >
            Reset
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div>
          <label className="block text-[11px] font-medium text-text-muted mb-1">
            Max Budget
          </label>
          <input
            type="number"
            min="1"
            step="0.01"
            value={maxPrice}
            onChange={(e) => onMaxPriceChange(e.target.value)}
            placeholder="No limit"
            className="w-full rounded-lg border border-border-subtle bg-bg-primary px-3 py-2 text-sm text-text-primary focus:border-[#16A36A] focus:outline-none tabular-nums"
          />
        </div>

        <div>
          <label className="block text-[11px] font-medium text-text-muted mb-1">
            Currency
          </label>
          <select
            value={currency}
            onChange={(e) => onCurrencyChange(e.target.value)}
            className="w-full rounded-lg border border-border-subtle bg-bg-primary px-3 py-2 text-sm text-text-primary focus:border-[#16A36A] focus:outline-none"
          >
            {SUPPORTED_CURRENCIES.map((cur) => (
              <option key={cur} value={cur}>
                {cur}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-medium text-text-muted mb-1">
            Category
          </label>
          <div className="relative">
            <select
              value={category}
              onChange={(e) => onCategoryChange(e.target.value)}
              className="w-full rounded-lg border border-border-subtle bg-bg-primary px-3 py-2 text-sm text-text-primary focus:border-[#16A36A] focus:outline-none"
            >
              <option value="ALL">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-[11px] font-medium text-text-muted mb-1">
            Sort Results
          </label>
          <div className="relative flex items-center">
            <Filter className="pointer-events-none absolute left-3 h-3.5 w-3.5 text-text-muted" />
            <select
              value={sortBy}
              onChange={(e) => onSortByChange(e.target.value)}
              className="w-full rounded-lg border border-border-subtle bg-bg-primary pl-8 pr-3 py-2 text-sm text-text-primary focus:border-[#16A36A] focus:outline-none"
            >
              <option value="relevance">Relevance</option>
              <option value="price_asc">Price: Low to High</option>
              <option value="price_desc">Price: High to Low</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}
