import React from "react";
import { AlertCircle, Inbox, RefreshCw } from "lucide-react";
import { Button } from "./Button";

export function Skeleton({ className = "h-4 w-full rounded-lg" }) {
  return <div className={`animate-skeleton ${className}`} aria-hidden="true" />;
}

export function CardSkeleton({ rows = 3 }) {
  return (
    <div className="rounded-xl border border-border-subtle bg-bg-card p-5 space-y-3 shadow-card">
      <Skeleton className="h-5 w-1/3 rounded-lg" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-4 w-full rounded-lg" />
      ))}
    </div>
  );
}

export function EmptyState({
  icon = null,
  title,
  description,
  action = null,
  className = "",
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center rounded-xl border border-dashed border-border-strong bg-bg-card px-6 py-10 ${className}`}
    >
      <div className="mb-3 rounded-lg border border-border-subtle bg-bg-secondary p-2.5 text-text-secondary">
        {icon || <Inbox className="h-5 w-5" />}
      </div>
      <h4 className="text-sm font-semibold text-text-primary">{title}</h4>
      {description && (
        <p className="mt-1 max-w-md text-xs text-text-secondary leading-relaxed">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Unable to load data",
  message = "An unexpected error occurred.",
  onRetry = null,
  className = "",
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center rounded-xl border border-[#FECDCA] bg-[#FEF3F2] px-6 py-8 dark:border-rose-500/30 dark:bg-rose-500/5 ${className}`}
    >
      <div className="mb-3 rounded-lg bg-[#FEE4E2] p-2.5 text-[#D92D20] dark:bg-rose-500/15 dark:text-rose-400">
        <AlertCircle className="h-5 w-5" />
      </div>
      <h4 className="text-sm font-semibold text-text-primary">{title}</h4>
      <p className="mt-1 max-w-md text-xs text-text-secondary">{message}</p>
      {onRetry && (
        <Button
          variant="secondary"
          size="sm"
          className="mt-4"
          icon={<RefreshCw className="h-3.5 w-3.5" />}
          onClick={onRetry}
        >
          Retry
        </Button>
      )}
    </div>
  );
}

