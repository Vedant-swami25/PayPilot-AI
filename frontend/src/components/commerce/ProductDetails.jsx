import React, { useState } from "react";
import {
  Check,
  ExternalLink,
  GitCompare,
  Package,
  ShieldCheck,
  ShoppingBag,
  Store,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { formatCurrency, getDisplayMoney } from "@/utils/formatCurrency";

export function ProductDetailsView({
  product,
  isCompared = false,
  onToggleCompare = null,
  onProceedToCheckout = null,
}) {
  const [imgError, setImgError] = useState(false);
  const [quantity, setQuantity] = useState(1);

  if (!product) return null;

  const inStock = (product.availability || "").toUpperCase() !== "OUT_OF_STOCK";
  const specEntries = Object.entries(product.specifications || {}).filter(
    ([k]) => k !== "data_origin"
  );

  // Grounded pros/cons strictly derived from product attributes
  const groundedPros = [];
  const groundedCons = [];
  if (inStock) groundedPros.push("Verified in stock by product provider.");
  else groundedCons.push(`Availability currently reported as ${product.availability}.`);
  if (product.merchant) groundedPros.push(`Merchant identified: ${product.merchant}.`);
  if (product.product_url) groundedPros.push("External merchant product URL available.");
  if (product.is_test_data)
    groundedCons.push("Marked as TEST DATA fixture (non-live inventory).");
  if (specEntries.length === 0)
    groundedCons.push("Limited technical specifications supplied by provider.");

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Gallery */}
      <Card padding="p-0" className="lg:col-span-5 overflow-hidden">
        <div className="h-80 sm:h-96 w-full bg-bg-secondary flex items-center justify-center">
          {product.image_url && !imgError ? (
            <img
              src={product.image_url}
              alt={product.name}
              onError={() => setImgError(true)}
              className="h-full w-full object-contain p-6 bg-[#F8FAFC] dark:bg-bg-secondary"
            />
          ) : (
            <div className="flex flex-col items-center gap-3 text-text-muted">
              <Package className="h-14 w-14 text-text-muted/60" />
              <span className="text-xs">No product image provided</span>
            </div>
          )}
        </div>
      </Card>

      {/* Details & Purchase Controls */}
      <div className="lg:col-span-7 space-y-5">
        <Card>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <Badge tone={inStock ? "emerald" : "red"}>{product.availability}</Badge>
            {product.category && <Badge tone="navy">{product.category}</Badge>}
            {product.is_test_data && <Badge tone="amber">Test Data</Badge>}
            <Badge tone="slate">Source: {product.provider}</Badge>
          </div>

          <h2 className="text-2xl font-semibold text-text-primary tracking-tight">
            {product.name}
          </h2>

          <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-text-secondary">
            <span className="inline-flex items-center gap-1.5">
              <Store className="h-4 w-4 text-text-muted" />
              Merchant: <strong className="text-text-primary">{product.merchant}</strong>
            </span>
            {product.product_url && (
              <a
                href={product.product_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[#16A36A] hover:underline text-xs font-medium"
              >
                <span>Merchant Listing</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </div>

          {(() => {
            const {
              displayPrice,
              displayCurrency,
              originalPrice,
              originalCurrency,
              hasConversion,
              exchangeRate,
            } = getDisplayMoney(product);
            return (
              <div className="mt-5 space-y-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-semibold text-text-primary tabular-nums">
                    {formatCurrency(displayPrice, displayCurrency)}
                  </span>
                  <span className="text-xs font-medium text-text-muted uppercase">
                    {displayCurrency} unit price
                  </span>
                </div>
                {hasConversion && (
                  <p className="text-xs text-text-secondary tabular-nums">
                    Original merchant price:{" "}
                    <strong className="text-text-primary">
                      {formatCurrency(originalPrice, originalCurrency)} {originalCurrency}
                    </strong>
                    {exchangeRate
                      ? ` (Rate: 1 ${originalCurrency} = ${Number(exchangeRate).toFixed(2)} ${displayCurrency})`
                      : ""}
                  </p>
                )}
              </div>
            );
          })()}

          {product.description && (
            <p className="mt-4 text-sm text-text-secondary leading-relaxed">
              {product.description}
            </p>
          )}

          <div className="mt-6 pt-5 border-t border-border-subtle flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-secondary px-3 py-1.5">
              <label htmlFor="detail-qty" className="text-xs text-text-muted">
                Qty
              </label>
              <input
                id="detail-qty"
                type="number"
                min={1}
                max={20}
                value={quantity}
                onChange={(e) =>
                  setQuantity(Math.min(20, Math.max(1, Number(e.target.value) || 1)))
                }
                className="w-12 bg-transparent text-sm font-medium text-text-primary focus:outline-none tabular-nums"
              />
            </div>

            {onProceedToCheckout && (
              <Button
                disabled={!inStock}
                onClick={() => onProceedToCheckout(product, quantity)}
                icon={<ShoppingBag className="h-4 w-4" />}
              >
                Proceed to PayPal Checkout
              </Button>
            )}

            {onToggleCompare && (
              <Button
                variant={isCompared ? "success" : "outline"}
                onClick={() => onToggleCompare(product.id)}
                icon={
                  isCompared ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <GitCompare className="h-4 w-4" />
                  )
                }
              >
                {isCompared ? "Selected for Comparison" : "Add to Compare"}
              </Button>
            )}
          </div>
          <p className="mt-2.5 flex items-center gap-1.5 text-[11px] text-text-muted">
            <ShieldCheck className="h-3.5 w-3.5 text-[#16A36A]" />
            Final order totals are calculated and verified on the server before PayPal order creation.
          </p>
        </Card>

        {/* Grounded Suitability & Specifications */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <h3 className="text-sm font-semibold text-text-primary mb-3">
              Verified Specifications
            </h3>
            {specEntries.length === 0 ? (
              <p className="text-xs text-text-muted">
                No structured specifications provided by external source.
              </p>
            ) : (
              <dl className="space-y-2 text-xs">
                {specEntries.map(([k, v]) => (
                  <div
                    key={k}
                    className="flex items-center justify-between gap-2 py-1 border-b border-border-subtle last:border-b-0"
                  >
                    <dt className="text-text-secondary capitalize">
                      {k.replaceAll("_", " ")}
                    </dt>
                    <dd className="font-mono text-text-primary text-right">
                      {typeof v === "boolean" ? (v ? "Yes" : "No") : String(v)}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </Card>

          <Card>
            <h3 className="text-sm font-semibold text-text-primary mb-3">
              Suitability & Check Summary
            </h3>
            <div className="space-y-3 text-xs">
              <div>
                <p className="font-semibold text-[#16A36A] mb-1">Verified Highlights</p>
                <ul className="space-y-1 text-text-secondary">
                  {groundedPros.map((item, i) => (
                    <li key={i}>• {item}</li>
                  ))}
                </ul>
              </div>
              {groundedCons.length > 0 && (
                <div>
                  <p className="font-semibold text-[#B54708] dark:text-amber-400 mb-1">Considerations</p>
                  <ul className="space-y-1 text-text-secondary">
                    {groundedCons.map((item, i) => (
                      <li key={i}>• {item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

