import React, { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, X } from "lucide-react";
import { Button } from "./Button";

export function Modal({
  open,
  onClose,
  title,
  description = null,
  children,
  maxWidth = "max-w-lg",
}) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
        >
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-[#101828]/45 backdrop-blur-[2px]"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.98, y: 6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: 6 }}
            transition={{ duration: 0.15 }}
            className={`relative z-10 w-full ${maxWidth} rounded-xl border border-border-subtle bg-bg-card p-6 shadow-elevated`}
          >
            <div className="flex items-start justify-between gap-4 mb-4">
              <div>
                <h3 className="text-lg font-semibold text-text-primary">
                  {title}
                </h3>
                {description && (
                  <p className="text-sm text-text-secondary mt-1">
                    {description}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close modal"
                className="rounded-lg p-1.5 text-text-secondary hover:bg-slate-500/15 hover:text-text-primary"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

export function ConfirmationDialog({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "primary",
  loading = false,
}) {
  return (
    <Modal open={open} onClose={onClose} title={title} maxWidth="max-w-md">
      <div className="flex items-start gap-3 text-sm text-text-secondary mb-6">
        <div className="rounded-lg bg-[#FFFAEB] border border-[#FEDF89] p-2 text-[#B54708] shrink-0 dark:bg-amber-500/15 dark:text-amber-400">
          <AlertTriangle className="h-5 w-5" />
        </div>
        <p className="leading-relaxed">{message}</p>
      </div>
      <div className="flex items-center justify-end gap-3">
        <Button variant="ghost" onClick={onClose} disabled={loading}>
          {cancelLabel}
        </Button>
        <Button variant={variant} onClick={onConfirm} loading={loading}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}

