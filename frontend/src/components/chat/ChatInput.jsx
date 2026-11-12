import React, { useState } from "react";
import { ArrowUp, DollarSign, Hash } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { SUPPORTED_CURRENCIES } from "@/utils/constants";

export function ChatInput({
  onSubmit,
  loading = false,
  disabled = false,
  placeholder = "Describe what you want to buy, specs, and budget...",
  defaultCurrency = "USD",
  initialText = "",
}) {
  const [text, setText] = useState(initialText);
  const [budget, setBudget] = useState("");
  const [currency, setCurrency] = useState(defaultCurrency);
  const [quantity, setQuantity] = useState(1);

  React.useEffect(() => {
    if (initialText) {
      setText(initialText);
    }
  }, [initialText]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const cleaned = text.trim();
    if (!cleaned || loading || disabled) return;
    onSubmit({
      requestText: cleaned,
      budget: budget ? Number(budget) : null,
      currency,
      quantity: Math.max(1, Number(quantity) || 1),
    });
    setText("");
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-border-strong bg-bg-card p-3 shadow-xs focus-within:border-[#16A36A] transition-colors"
    >
      <textarea
        rows={2}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
          }
        }}
        placeholder={placeholder}
        disabled={loading || disabled}
        className="w-full resize-none bg-transparent px-1 py-1 text-sm text-text-primary placeholder:text-text-muted focus:outline-none"
      />

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border-subtle">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1 rounded-lg border border-border-subtle bg-bg-primary px-2 py-1">
            <DollarSign className="h-3.5 w-3.5 text-text-muted" />
            <input
              type="number"
              min="1"
              step="0.01"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="Max budget"
              aria-label="Maximum budget"
              className="w-24 bg-transparent text-xs text-text-primary placeholder:text-text-muted focus:outline-none tabular-nums"
            />
          </div>

          <select
            aria-label="Currency"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="rounded-lg border border-border-subtle bg-bg-primary px-2 py-1 text-xs text-text-primary focus:outline-none"
          >
            {SUPPORTED_CURRENCIES.map((cur) => (
              <option key={cur} value={cur}>
                {cur}
              </option>
            ))}
          </select>

          <div className="flex items-center gap-1 rounded-lg border border-border-subtle bg-bg-primary px-2 py-1">
            <Hash className="h-3.5 w-3.5 text-text-muted" />
            <input
              type="number"
              min="1"
              max="20"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              aria-label="Quantity"
              className="w-12 bg-transparent text-xs text-text-primary focus:outline-none tabular-nums"
            />
          </div>
        </div>

        <Button
          type="submit"
          size="sm"
          loading={loading}
          disabled={!text.trim() || disabled}
          icon={<ArrowUp className="h-3.5 w-3.5" />}
        >
          Search
        </Button>
      </div>
    </form>
  );
}
