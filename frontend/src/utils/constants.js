export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/+$/, "");

export const PAYPAL_CLIENT_ID = (
  import.meta.env.VITE_PAYPAL_CLIENT_ID || ""
).trim();

export const SHOPPING_STEP_META = {
  LEAD_AGENT: "Understanding your request",
  DISCOVERY_AGENT: "Searching live merchant listings",
  COMPARISON_AGENT: "Comparing prices and specifications",
  DECISION_AGENT: "Selecting the strongest match",
  SECURITY_AGENT: "Verifying spending limits and safety checks",
  USER_APPROVAL: "Waiting for your purchase confirmation",
  PAYMENT_AGENT: "Preparing PayPal checkout",
  MONITORING_AGENT: "Finalizing order details",
};

export const WORKFLOW_STATUS_META = {
  PENDING: { label: "Starting", tone: "purple" },
  RUNNING: { label: "Searching", tone: "purple" },
  NEEDS_CLARIFICATION: {
    label: "Needs Details",
    tone: "amber",
  },
  NO_PRODUCTS_FOUND: {
    label: "No Matches Found",
    tone: "amber",
  },
  AWAITING_USER_APPROVAL: {
    label: "Ready for Review",
    tone: "cyan",
  },
  APPROVED: { label: "Approved", tone: "emerald" },
  ORDER_CREATED: {
    label: "Checkout Ready",
    tone: "cyan",
  },
  COMPLETED: {
    label: "Completed",
    tone: "emerald",
  },
  BLOCKED_BY_SECURITY: {
    label: "Blocked by Limit",
    tone: "red",
  },
  FAILED: { label: "Unavailable", tone: "red" },
  NOT_CONFIGURED: {
    label: "Service Unavailable",
    tone: "amber",
  },
  CANCELLED: { label: "Cancelled", tone: "slate" },
};

export const PAYMENT_STATUS_META = {
  CREATED: { label: "Created", tone: "slate" },
  PENDING_APPROVAL: { label: "Awaiting PayPal Approval", tone: "amber" },
  APPROVED: { label: "PayPal Approved", tone: "cyan" },
  CAPTURE_PENDING: { label: "Capture Pending", tone: "purple" },
  COMPLETED: { label: "Completed", tone: "emerald" },
  FAILED: { label: "Failed", tone: "red" },
  CANCELLED: { label: "Cancelled", tone: "slate" },
  REFUNDED: { label: "Refunded", tone: "amber" },
};

export const SUPPORTED_CURRENCIES = ["USD", "EUR", "GBP", "CAD", "AUD", "INR", "SGD", "JPY"];

export const SUGGESTED_PROMPTS = [
  "Find me a laptop for AI development under $1,000 USD",
  "Find noise cancelling wireless headphones under $300 USD",
  "Compare mechanical keyboards under $200 USD with hot-swappable switches",
  "Find a dual-4K Thunderbolt USB-C docking station under $180 USD",
];

