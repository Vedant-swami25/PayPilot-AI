import React from "react";

export function Card({
  children,
  className = "",
  glow = false,
  hover = false,
  padding = "p-5",
  ...props
}) {
  return (
    <div
      className={`rounded-xl border ${
        glow ? "border-border-strong shadow-elevated" : "border-border-subtle shadow-card"
      } bg-bg-card transition-colors duration-150 ${
        hover ? "hover:border-border-strong" : ""
      } ${padding} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action, className = "" }) {
  return (
    <div className={`flex items-start justify-between gap-4 mb-4 ${className}`}>
      <div>
        <h3 className="text-base font-semibold text-text-primary tracking-tight">
          {title}
        </h3>
        {subtitle && (
          <p className="text-xs text-text-secondary mt-0.5">{subtitle}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
