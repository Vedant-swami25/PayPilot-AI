import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Info,
  X,
  XCircle,
} from "lucide-react";
import { useAppStore } from "@/store/useAppStore";

const ICON_MAP = {
  success: { icon: CheckCircle2, color: "text-[#12B76A]", border: "border-[#ABEFC6]" },
  error: { icon: XCircle, color: "text-[#D92D20]", border: "border-[#FECDCA]" },
  warning: { icon: AlertTriangle, color: "text-[#DC6803]", border: "border-[#FEDF89]" },
  info: { icon: Info, color: "text-[#101828] dark:text-slate-200", border: "border-border-strong" },
};

export function ToastContainer() {
  const toasts = useAppStore((s) => s.toasts);
  const dismissToast = useAppStore((s) => s.dismissToast);

  return (
    <div
      aria-live="polite"
      className="fixed bottom-4 right-4 z-[70] flex flex-col gap-2.5 w-full max-w-sm pointer-events-none px-4 sm:px-0"
    >
      <AnimatePresence>
        {toasts.map((toast) => {
          const cfg = ICON_MAP[toast.variant] || ICON_MAP.info;
          const Icon = cfg.icon;
          return (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 16, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.96 }}
              className={`pointer-events-auto flex items-start gap-3 rounded-xl border ${cfg.border} bg-bg-card p-3.5 shadow-elevated`}
            >
              <Icon className={`h-5 w-5 shrink-0 mt-0.5 ${cfg.color}`} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text-primary">
                  {toast.title}
                </p>
                {toast.description && (
                  <p className="text-xs text-text-secondary mt-0.5 break-words">
                    {toast.description}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismissToast(toast.id)}
                aria-label="Dismiss notification"
                className="text-text-muted hover:text-text-primary p-0.5"
              >
                <X className="h-4 w-4" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}

export function Dropdown({
  trigger,
  items = [],
  align = "right",
  className = "",
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, []);

  return (
    <div ref={ref} className={`relative inline-block ${className}`}>
      <div onClick={() => setOpen((v) => !v)}>{trigger}</div>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.97 }}
            transition={{ duration: 0.14 }}
            className={`absolute ${
              align === "left" ? "left-0" : "right-0"
            } z-40 mt-2 w-56 rounded-xl border border-border-subtle bg-bg-card p-1.5 shadow-elevated`}
          >
            {items.map((item, idx) =>
              item.divider ? (
                <div key={idx} className="my-1 border-t border-border-subtle" />
              ) : (
                <button
                  key={item.label || idx}
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    item.onClick?.();
                  }}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-xs font-medium transition-colors ${
                    item.danger
                      ? "text-[#D92D20] hover:bg-[#FEF3F2] dark:text-rose-400 dark:hover:bg-rose-500/10"
                      : "text-text-primary hover:bg-bg-secondary"
                  }`}
                >
                  {item.icon && <span className="shrink-0">{item.icon}</span>}
                  <span>{item.label}</span>
                </button>
              )
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function SelectDropdown({
  value,
  onChange,
  options = [],
  className = "",
  ariaLabel = "Select option",
}) {
  return (
    <div className={`relative inline-flex items-center ${className}`}>
      <select
        aria-label={ariaLabel}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full appearance-none rounded-lg border border-border-subtle bg-bg-card px-3.5 py-2 pr-9 text-sm text-text-primary focus:border-[#16A36A] focus:outline-none"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 h-4 w-4 text-text-secondary" />
    </div>
  );
}

