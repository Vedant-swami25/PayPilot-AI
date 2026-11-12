import React from "react";

/**
 * PayPilot brand monogram mark rendering the official logo asset (/logo.jpg).
 */
export function PayPilotMark({
  className = "h-8 w-8",
  decorative = false,
}) {
  return (
    <img
      src="/logo.jpg"
      alt={decorative ? "" : "PayPilot"}
      aria-hidden={decorative ? "true" : undefined}
      className={`${className} rounded-lg object-cover shrink-0 shadow-xs`}
    />
  );
}

/**
 * Full PayPilot lockup (brand mark + PayPilot wordmark) with compact symbol variant.
 */
export function PayPilotLogo({
  variant = "full",
  surface = "auto",
  size = "md",
  className = "",
}) {
  const markSizes = {
    sm: "h-7 w-7",
    md: "h-8 w-8",
    lg: "h-10 w-10",
  };
  const textSizes = {
    sm: "text-base",
    md: "text-[17px]",
    lg: "text-xl",
  };

  const wordmarkColor =
    surface === "dark"
      ? "text-white"
      : surface === "light"
        ? "text-[#101828]"
        : "text-text-primary";

  return (
    <span className={`inline-flex items-center gap-2.5 select-none ${className}`}>
      <PayPilotMark
        className={markSizes[size] || markSizes.md}
        decorative={variant === "full"}
      />
      {variant === "full" && (
        <span className="inline-flex items-baseline gap-1.5">
          <span
            className={`font-semibold tracking-tight leading-none ${
              textSizes[size] || textSizes.md
            } ${wordmarkColor}`}
          >
            PayPilot
          </span>
          <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider bg-[#16A36A]/10 text-[#16A36A]">
            AI
          </span>
        </span>
      )}
    </span>
  );
}
