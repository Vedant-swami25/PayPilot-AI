import React from "react";
import { Loader2 } from "lucide-react";

export function TypingIndicator({ label = "Searching and comparing products..." }) {
  return (
    <div className="inline-flex items-center gap-2.5 rounded-xl border border-border-subtle bg-bg-primary px-3.5 py-2.5 text-xs text-text-secondary">
      <Loader2 className="h-3.5 w-3.5 animate-spin text-[#16A36A] shrink-0" />
      <span>{label}</span>
    </div>
  );
}

