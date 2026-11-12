import React from "react";
import { Loader2 } from "lucide-react";

const VARIANT_CLASSES = {
  primary:
    "bg-[#101828] text-white hover:bg-[#1D2939] border border-[#101828] shadow-xs dark:bg-[#16A36A] dark:border-[#16A36A] dark:hover:bg-[#12B76A]",
  emerald:
    "bg-[#16A36A] text-white hover:bg-[#138D5B] border border-[#16A36A] shadow-xs",
  secondary:
    "bg-bg-card text-text-primary border border-border-strong hover:bg-bg-secondary shadow-xs",
  outline:
    "bg-transparent text-text-primary border border-border-strong hover:bg-bg-secondary",
  ghost:
    "bg-transparent text-text-secondary hover:text-text-primary hover:bg-bg-secondary border border-transparent",
  danger:
    "bg-[#FEF3F2] text-[#D92D20] border border-[#FECDCA] hover:bg-[#FEE4E2] dark:bg-rose-500/15 dark:text-rose-300 dark:border-rose-500/35",
  success:
    "bg-[#ECFDF3] text-[#067647] border border-[#ABEFC6] hover:bg-[#D1FADF] dark:bg-emerald-500/15 dark:text-emerald-300 dark:border-emerald-500/35",
};

const SIZE_CLASSES = {
  xs: "px-2.5 py-1.5 text-xs rounded-lg gap-1.5",
  sm: "px-3 py-1.5 text-xs font-medium rounded-lg gap-1.5",
  md: "px-4 py-2 text-sm font-medium rounded-lg gap-2",
  lg: "px-5 py-2.5 text-sm font-semibold rounded-lg gap-2",
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  icon = null,
  className = "",
  type = "button",
  ...props
}) {
  const isDisabled = disabled || loading;

  return (
    <button
      type={type}
      disabled={isDisabled}
      className={`inline-flex items-center justify-center font-medium transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#16A36A]/50 disabled:opacity-50 disabled:cursor-not-allowed ${
        VARIANT_CLASSES[variant] || VARIANT_CLASSES.primary
      } ${SIZE_CLASSES[size] || SIZE_CLASSES.md} ${className}`}
      {...props}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin shrink-0" />
      ) : icon ? (
        <span className="shrink-0">{icon}</span>
      ) : null}
      {children}
    </button>
  );
}
