import React from "react";

const TONE_MAP = {
  emerald:
    "bg-[#ECFDF3] text-[#067647] border-[#ABEFC6] dark:bg-emerald-500/15 dark:text-emerald-300 dark:border-emerald-500/30",
  navy:
    "bg-[#F2F4F7] text-[#101828] border-[#D0D5DD] dark:bg-slate-700/40 dark:text-slate-100 dark:border-slate-600",
  amber:
    "bg-[#FFFAEB] text-[#B54708] border-[#FEDF89] dark:bg-amber-500/15 dark:text-amber-300 dark:border-amber-500/30",
  red:
    "bg-[#FEF3F2] text-[#B42318] border-[#FECDCA] dark:bg-rose-500/15 dark:text-rose-300 dark:border-rose-500/30",
  slate:
    "bg-bg-secondary text-text-secondary border-border-subtle",
  // Legacy tone aliases mapped cleanly to FinTech semantic palette
  purple:
    "bg-[#ECFDF3] text-[#067647] border-[#ABEFC6] dark:bg-emerald-500/15 dark:text-emerald-300 dark:border-emerald-500/30",
  cyan:
    "bg-[#F2F4F7] text-[#344054] border-[#D0D5DD] dark:bg-slate-700/40 dark:text-slate-200 dark:border-slate-600",
};

export function Badge({
  children,
  tone = "slate",
  dot = false,
  pulse = false,
  className = "",
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium ${
        TONE_MAP[tone] || TONE_MAP.slate
      } ${className}`}
    >
      {dot && (
        <span
          className={`h-1.5 w-1.5 rounded-full bg-current ${
            pulse ? "animate-pulse" : ""
          }`}
        />
      )}
      {children}
    </span>
  );
}

export function Tooltip({ content, children, className = "" }) {
  return (
    <span className={`group relative inline-flex ${className}`}>
      {children}
      {content && (
        <span
          role="tooltip"
          className="pointer-events-none absolute bottom-full left-1/2 z-40 mb-2 -translate-x-1/2 whitespace-nowrap rounded-lg border border-border-subtle bg-[#101828] px-2.5 py-1 text-xs text-white opacity-0 shadow-elevated transition-opacity duration-150 group-hover:opacity-100"
        >
          {content}
        </span>
      )}
    </span>
  );
}
