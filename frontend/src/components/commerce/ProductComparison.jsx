import React from "react";
import { CheckCircle2, MinusCircle } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { formatCurrency, getDisplayMoney } from "@/utils/formatCurrency";

const PRIORITY_SPEC_KEYS = [
  "brand",
  "processor",
  "cpu",
  "ram",
  "memory",
  "storage",
  "gpu",
  "graphics",
  "battery_hours",
  "bluetooth",
  "anc",
  "layout",
];

export function ProductComparison({ comparison, onSelectProduct = null }) {
  if (!comparison || !comparison.items?.length) return null;

  const items = comparison.items;

  const allSpecKeys = Array.from(
    new Set(
      items.flatMap((item) =>
        Object.keys(item.specifications || {}).filter((k) => k !== "data_origin")
      )
    )
  ).sort((a, b) => {
    const ai = PRIORITY_SPEC_KEYS.indexOf(a.toLowerCase());
    const bi = PRIORITY_SPEC_KEYS.indexOf(b.toLowerCase());
    if (ai !== -1 && bi !== -1) return ai - bi;
    if (ai !== -1) return -1;
    if (bi !== -1) return 1;
    return a.localeCompare(b);
  });

  return (
    <div className="space-y-6">
      {/* Side-by-Side Product Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {items.map((item) => {
          const isBest = item.product_id === comparison.best_value_product_id;
          return (
            <Card
              key={item.product_id}
              glow={isBest}
              className={`flex flex-col justify-between gap-4 ${
                isBest ? "border-[#16A36A] dark:border-[#16A36A]" : ""
              }`}
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  {isBest ? (
                    <Badge tone="emerald">Best Overall Match</Badge>
                  ) : (
                    <Badge tone="slate">Option</Badge>
                  )}
                  <span className="text-xs font-medium text-text-muted tabular-nums">
                    {Number(item.requirement_match_score) <= 1
                      ? Math.round(Number(item.requirement_match_score) * 100)
                      : Math.round(Number(item.requirement_match_score))}
                    % match
                  </span>
                </div>
                <h3 className="text-sm font-semibold text-text-primary leading-snug line-clamp-2">
                  {item.name}
                </h3>
                <p className="text-xs text-text-secondary">{item.merchant}</p>
              </div>

              <div className="space-y-3 pt-2 border-t border-border-subtle">
                {(() => {
                  const money = getDisplayMoney(item);
                  return (
                    <div>
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-xl font-semibold text-text-primary tabular-nums">
                          {formatCurrency(money.displayPrice, money.displayCurrency)}
                        </span>
                        {Number(item.price_delta_from_lowest) === 0 ? (
                          <span className="text-[11px] font-medium text-[#16A36A]">
                            Lowest price
                          </span>
                        ) : (
                          <span className="text-[11px] text-text-muted tabular-nums">
                            +{formatCurrency(item.price_delta_from_lowest, money.displayCurrency)}
                          </span>
                        )}
                      </div>
                      {money.hasConversion && (
                        <p className="text-[11px] text-text-muted tabular-nums mt-0.5">
                          Merchant: {formatCurrency(money.originalPrice, money.originalCurrency)}{" "}
                          {money.originalCurrency}
                        </p>
                      )}
                    </div>
                  );
                })()}

                {onSelectProduct && (
                  <Button
                    size="sm"
                    variant={isBest ? "primary" : "secondary"}
                    className="w-full"
                    onClick={() => onSelectProduct(item)}
                  >
                    Select &amp; Checkout
                  </Button>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      {/* Price Summary Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card padding="p-4">
          <p className="text-xs text-text-muted">Lowest Price</p>
          <p className="mt-1 text-lg font-semibold text-[#16A36A] tabular-nums">
            {formatCurrency(comparison.lowest_price, comparison.currency)}
          </p>
        </Card>
        <Card padding="p-4">
          <p className="text-xs text-text-muted">Highest Price</p>
          <p className="mt-1 text-lg font-semibold text-text-primary tabular-nums">
            {formatCurrency(comparison.highest_price, comparison.currency)}
          </p>
        </Card>
        <Card padding="p-4">
          <p className="text-xs text-text-muted">Average Price</p>
          <p className="mt-1 text-lg font-semibold text-text-primary tabular-nums">
            {formatCurrency(comparison.average_price, comparison.currency)}
          </p>
        </Card>
        <Card padding="p-4">
          <p className="text-xs text-text-muted">Price Spread</p>
          <p className="mt-1 text-lg font-semibold text-text-secondary tabular-nums">
            {formatCurrency(comparison.price_spread, comparison.currency)}
          </p>
        </Card>
      </div>

      {/* Recommendation Summary & Specification Matrix */}
      <Card padding="p-0" className="overflow-hidden">
        <div className="p-5 border-b border-border-subtle">
          <CardHeader
            title="Specification & Value Breakdown"
            subtitle={comparison.summary}
            className="mb-0"
          />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border-collapse">
            <thead>
              <tr className="border-b border-border-subtle bg-bg-secondary">
                <th className="p-4 text-xs font-semibold uppercase tracking-wider text-text-muted min-w-[160px]">
                  Attribute
                </th>
                {items.map((item) => {
                  const isBest = item.product_id === comparison.best_value_product_id;
                  return (
                    <th
                      key={item.product_id}
                      className={`p-4 min-w-[220px] align-top ${
                        isBest ? "bg-[#ECFDF3]/60 dark:bg-emerald-500/10" : ""
                      }`}
                    >
                      <div className="space-y-1">
                        <p className="font-semibold text-text-primary leading-snug">
                          {item.name}
                        </p>
                        {isBest && (
                          <span className="inline-block text-[11px] font-medium text-[#16A36A]">
                            Best Value Recommendation
                          </span>
                        )}
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>

            <tbody className="divide-y divide-border-subtle">
              <tr>
                <td className="p-4 text-xs font-medium text-text-secondary">
                  Price
                </td>
                {items.map((item) => {
                  const money = getDisplayMoney(item);
                  return (
                    <td
                      key={item.product_id}
                      className="p-4 font-semibold text-text-primary tabular-nums"
                    >
                      <div>{formatCurrency(money.displayPrice, money.displayCurrency)}</div>
                      {money.hasConversion && (
                        <div className="text-[11px] font-normal text-text-muted mt-0.5">
                          Merchant: {formatCurrency(money.originalPrice, money.originalCurrency)}{" "}
                          {money.originalCurrency}
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>

              <tr>
                <td className="p-4 text-xs font-medium text-text-secondary">
                  Price Difference
                </td>
                {items.map((item) => (
                  <td key={item.product_id} className="p-4 text-xs tabular-nums">
                    {Number(item.price_delta_from_lowest) === 0 ? (
                      <Badge tone="emerald">Lowest Price</Badge>
                    ) : (
                      <span className="text-text-secondary">
                        +{formatCurrency(item.price_delta_from_lowest, item.currency)}{" "}
                        (+{item.price_delta_percent}%)
                      </span>
                    )}
                  </td>
                ))}
              </tr>

              <tr>
                <td className="p-4 text-xs font-medium text-text-secondary">
                  Merchant
                </td>
                {items.map((item) => (
                  <td key={item.product_id} className="p-4 text-xs text-text-primary">
                    {item.merchant}
                  </td>
                ))}
              </tr>

              <tr>
                <td className="p-4 text-xs font-medium text-text-secondary">
                  Availability
                </td>
                {items.map((item) => (
                  <td key={item.product_id} className="p-4">
                    <Badge
                      tone={
                        item.availability?.toUpperCase() === "IN_STOCK"
                          ? "emerald"
                          : "red"
                      }
                    >
                      {item.availability}
                    </Badge>
                  </td>
                ))}
              </tr>

              {allSpecKeys.map((specKey) => (
                <tr key={specKey}>
                  <td className="p-4 text-xs font-medium text-text-secondary capitalize">
                    {specKey.replaceAll("_", " ")}
                  </td>
                  {items.map((item) => {
                    const val = item.specifications?.[specKey];
                    return (
                      <td
                        key={item.product_id}
                        className="p-4 text-xs text-text-primary"
                      >
                        {val === undefined || val === null
                          ? "—"
                          : typeof val === "boolean"
                            ? val
                              ? "Yes"
                              : "No"
                            : Array.isArray(val)
                              ? val.join(", ")
                              : String(val)}
                      </td>
                    );
                  })}
                </tr>
              ))}

              <tr>
                <td className="p-4 text-xs font-medium text-text-secondary align-top">
                  Key Strengths
                </td>
                {items.map((item) => (
                  <td key={item.product_id} className="p-4 align-top">
                    <ul className="space-y-1.5 text-xs text-[#067647] dark:text-emerald-300">
                      {item.pros?.map((pro, idx) => (
                        <li key={idx} className="flex items-start gap-1.5">
                          <CheckCircle2 className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                          <span>{pro}</span>
                        </li>
                      ))}
                    </ul>
                  </td>
                ))}
              </tr>

              <tr>
                <td className="p-4 text-xs font-medium text-text-secondary align-top">
                  Considerations
                </td>
                {items.map((item) => (
                  <td key={item.product_id} className="p-4 align-top">
                    {item.cons?.length ? (
                      <ul className="space-y-1.5 text-xs text-[#B54708] dark:text-amber-300">
                        {item.cons.map((con, idx) => (
                          <li key={idx} className="flex items-start gap-1.5">
                            <MinusCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                            <span>{con}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <span className="text-xs text-text-muted">None noted</span>
                    )}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
