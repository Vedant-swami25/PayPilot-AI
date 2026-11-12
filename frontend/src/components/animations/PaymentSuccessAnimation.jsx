import React from "react";
import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import { formatCurrency } from "@/utils/formatCurrency";

export function PaymentSuccessAnimation({
  transactionId,
  paypalOrderId,
  amount,
  currency = "USD",
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.25 }}
      className="relative flex flex-col items-center justify-center rounded-xl border border-emerald-200 dark:border-emerald-500/30 bg-bg-card p-8 text-center shadow-card"
    >
      {/* Crisp FinTech Checkmark Badge */}
      <div className="relative mb-5 flex h-16 w-16 items-center justify-center">
        <motion.div
          initial={{ scale: 0.85, opacity: 0.5 }}
          animate={{ scale: 1.25, opacity: 0 }}
          transition={{ duration: 0.9, ease: "easeOut" }}
          className="absolute inset-0 rounded-full border border-[#12B76A]"
        />
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-50 dark:bg-emerald-500/15 border border-emerald-200 dark:border-emerald-500/30">
          <svg
            viewBox="0 0 36 36"
            className="h-8 w-8 text-[#12B76A]"
            fill="none"
          >
            <path
              d="M8 18.5L15 25.5L28.5 11"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="animate-check-draw"
            />
          </svg>
        </div>
      </div>

      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 dark:bg-emerald-500/15 border border-emerald-200 dark:border-emerald-500/30 px-3 py-1 text-xs font-medium text-[#067647] dark:text-emerald-300 mb-2">
        <ShieldCheck className="h-3.5 w-3.5" />
        Verified PayPal Capture Completed
      </span>

      <h3 className="text-xl font-bold text-text-primary">
        Payment Confirmed
      </h3>
      <p className="mt-1 text-2xl font-bold font-mono text-[#16A36A] tabular-nums">
        {formatCurrency(amount, currency)}
      </p>

      <div className="mt-5 w-full max-w-sm rounded-xl border border-border-subtle bg-bg-secondary p-3.5 text-left text-xs space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-text-secondary">Order / Transaction Ref</span>
          <span className="font-mono text-text-primary truncate max-w-[180px]">
            {transactionId}
          </span>
        </div>
        {paypalOrderId && (
          <div className="flex items-center justify-between gap-2">
            <span className="text-text-secondary">PayPal Order ID</span>
            <span className="font-mono font-medium text-text-primary">{paypalOrderId}</span>
          </div>
        )}
      </div>
    </motion.div>
  );
}
