import React, { useState } from "react";
import { Link } from "react-router-dom";
import {
  Check,
  ExternalLink,
  GitCompare,
  Package,
  ShoppingCart,
  Store,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { formatCurrency, getDisplayMoney } from "@/utils/formatCurrency";

export function RecommendationBadge({ label = "Recommended" }) {
  return <Badge tone="emerald">{label}</Badge>;
}

export function ProductCard({
  product,
  isRecommended = false,
  isCompared = false,
  onToggleCompare = null,
  onSelectForCheckout = null,
}) {
  const [imgError, setImgError] = useState(false);
  const inStock = (product.availability || "").toUpperCase() !== "OUT_OF_STOCK";
  const brand =
    product.brand ||
    product.specifications?.brand ||
    product.specifications?.manufacturer ||
    null;
  const {
    displayPrice,
    displayCurrency,
    originalPrice,
    originalCurrency,
    hasConversion,
  } = getDisplayMoney(product);
  const detailsUrl = `/products/${encodeURIComponent(product.id)}${
    displayCurrency ? `?currency=${encodeURIComponent(displayCurrency)}` : ""
  }`;

  return (
    <Card
      hover
      glow={isRecommended}
      padding="p-0"
      className="flex flex-col overflow-hidden h-full"
    >
      <div className="relative aspect-[4/3] w-full bg-[#F8FAFC] dark:bg-bg-secondary flex items-center justify-center overflow-hidden border-b border-border-subtle p-4">
        {product.image_url && !imgError ? (
          <img
            src={product.image_url}
            alt={product.name}
            onError={() => setImgError(true)}
            className="max-h-full max-w-full object-contain transition-transform duration-200 hover:scale-[1.02]"
          />
        ) : (
          <div className="flex flex-col items-center gap-2 text-text-muted">
            <Package className="h-9 w-9 text-text-muted/60" />
            <span className="text-xs">No image available</span>
          </div>
        )}

        <div className="absolute left-3 top-3 flex flex-wrap gap-1.5">
          {isRecommended && <RecommendationBadge />}
          {product.is_test_data && <Badge tone="amber">Test Data</Badge>}
        </div>

        <div className="absolute right-3 top-3">
          <Badge tone={inStock ? "emerald" : "red"}>
            {inStock ? "In Stock" : "Out of Stock"}
          </Badge>
        </div>
      </div>

      <div className="flex flex-1 flex-col p-4">
        <div className="flex items-center justify-between gap-2 text-xs text-text-muted mb-1">
          <span className="font-medium text-text-secondary truncate">
            {brand || product.category || "Verified Catalog"}
          </span>
          {product.category && brand && (
            <span className="rounded bg-bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-text-secondary">
              {product.category}
            </span>
          )}
        </div>

        <Link
          to={detailsUrl}
          className="text-sm font-semibold text-text-primary hover:text-[#16A36A] transition-colors line-clamp-2 leading-snug"
        >
          {product.name}
        </Link>

        <p className="mt-1.5 inline-flex items-center gap-1.5 text-xs text-text-secondary truncate">
          <Store className="h-3.5 w-3.5 text-text-muted shrink-0" />
          <span className="truncate">{product.merchant || "Verified Merchant"}</span>
        </p>

        {product.description && (
          <p className="mt-2 text-xs text-text-muted line-clamp-2 flex-1">
            {product.description}
          </p>
        )}

        <div className="mt-4 pt-3 border-t border-border-subtle space-y-3">
          <div>
            <div className="flex items-baseline justify-between gap-2">
              <p className="text-lg font-semibold text-text-primary tabular-nums">
                {formatCurrency(displayPrice, displayCurrency)}
              </p>
              <span className="text-[11px] font-medium text-text-muted uppercase">
                {displayCurrency}
              </span>
            </div>
            {hasConversion && (
              <p className="text-[11px] text-text-muted tabular-nums mt-0.5">
                Merchant: {formatCurrency(originalPrice, originalCurrency)} {originalCurrency}
              </p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={detailsUrl}
              className="flex-1 min-w-[84px]"
            >
              <Button
                size="xs"
                variant="secondary"
                className="w-full"
                icon={<ExternalLink className="h-3.5 w-3.5" />}
              >
                Details
              </Button>
            </Link>

            {onToggleCompare && (
              <Button
                variant={isCompared ? "success" : "outline"}
                size="xs"
                onClick={() => onToggleCompare(product.id)}
                title={isCompared ? "Remove from comparison" : "Add to comparison"}
                icon={
                  isCompared ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : (
                    <GitCompare className="h-3.5 w-3.5" />
                  )
                }
              >
                {isCompared ? "Comparing" : "Compare"}
              </Button>
            )}

            {onSelectForCheckout && (
              <Button
                size="xs"
                variant="primary"
                disabled={!inStock}
                onClick={() => onSelectForCheckout(product)}
                icon={<ShoppingCart className="h-3.5 w-3.5" />}
              >
                Buy
              </Button>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

export function ProductGrid({
  products = [],
  recommendedProductId = null,
  compareIds = [],
  onToggleCompare = null,
  onSelectForCheckout = null,
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
      {products.map((product) => (
        <ProductCard
          key={product.id}
          product={product}
          isRecommended={product.id === recommendedProductId}
          isCompared={compareIds.includes(product.id)}
          onToggleCompare={onToggleCompare}
          onSelectForCheckout={onSelectForCheckout}
        />
      ))}
    </div>
  );
}
