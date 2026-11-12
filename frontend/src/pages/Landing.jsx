import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  CreditCard,
  Lock,
  Scale,
  Search,
  ShieldCheck,
  ShoppingBag,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { PayPilotLogo } from "@/components/ui/Logo";
import { useAuth } from "@/hooks/useAuth";

const SAMPLE_SEARCHES = [
  {
    id: "laptop",
    label: "Workstation < $1,000",
    prompt: "Find me a laptop for AI development under $1,000 USD",
    stages: [
      { title: "Parsed Preferences", detail: "Budget cap $1,000 USD • High memory & GPU specs" },
      { title: "Merchant Search", detail: "Scanned live merchant listings • 6 in-stock options found" },
      { title: "Price Comparison", detail: "Compared price range ($849 – $999) • Saved $150" },
      { title: "Spending Protection", detail: "Verified merchant • Within single-order limit" },
    ],
    recommendation: {
      name: "Lenovo IdeaPad Pro 5i (RTX 3050 / 16GB / 1TB)",
      price: "$899.00",
      score: "96% Match",
      merchant: "Authorized Electronics Partner",
    },
  },
  {
    id: "headphones",
    label: "ANC Headphones < $300",
    prompt: "Find noise cancelling wireless headphones under $300 USD",
    stages: [
      { title: "Parsed Preferences", detail: "Budget cap $300 USD • Active noise cancellation" },
      { title: "Merchant Search", detail: "Fetched verified offers • 4 models compared" },
      { title: "Price Comparison", detail: "Identified up to $65 savings across merchants" },
      { title: "Spending Protection", detail: "Passed limit check • Confirmation required before pay" },
    ],
    recommendation: {
      name: "Sony WH-1000XM5 Wireless Noise Cancelling",
      price: "$278.00",
      score: "94% Match",
      merchant: "Verified Audio Store",
    },
  },
];

const WORKFLOW_STEPS = [
  {
    step: "01",
    icon: Search,
    title: "Describe What You Want",
    description:
      "Enter natural shopping criteria, preferred specs, and a budget cap — no complex filter menus required.",
  },
  {
    step: "02",
    icon: Scale,
    title: "Compare Verified Offers",
    description:
      "PayPilot retrieves real-time merchant listings, normalizes pricing, and highlights value trade-offs side by side.",
  },
  {
    step: "03",
    icon: ShieldCheck,
    title: "Approve & Pay via PayPal",
    description:
      "Your spending limits are verified automatically, and payments execute only after your explicit confirmation.",
  },
];

export default function Landing() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [heroPrompt, setHeroPrompt] = useState(
    "Find me a laptop for AI development under $1,000 USD"
  );
  const [activeScenarioId, setActiveScenarioId] = useState("laptop");

  const scenario =
    SAMPLE_SEARCHES.find((s) => s.id === activeScenarioId) || SAMPLE_SEARCHES[0];

  const handleLaunchPrompt = (e) => {
    e.preventDefault();
    const encoded = encodeURIComponent(heroPrompt.trim());
    if (isAuthenticated) {
      navigate(`/command-center?prompt=${encoded}`);
    } else {
      navigate(`/register?prompt=${encoded}`);
    }
  };

  return (
    <div className="min-h-screen bg-bg-primary text-text-primary overflow-x-hidden">
      {/* Top Navigation */}
      <header className="sticky top-0 z-40 border-b border-border-subtle bg-bg-card/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link to="/" className="flex items-center">
            <PayPilotLogo variant="full" surface="auto" size="md" />
          </Link>

          <nav className="hidden md:flex items-center gap-7 text-sm font-medium text-text-secondary">
            <a href="#how-it-works" className="hover:text-text-primary transition-colors">
              How It Works
            </a>
            <a href="#demo" className="hover:text-text-primary transition-colors">
              Smart Comparison
            </a>
            <a href="#security" className="hover:text-text-primary transition-colors">
              Security & Limits
            </a>
          </nav>

          <div className="flex items-center gap-2.5">
            {isAuthenticated ? (
              <Link to="/dashboard">
                <Button variant="primary" size="sm" icon={<ArrowRight className="h-4 w-4" />}>
                  Open Dashboard
                </Button>
              </Link>
            ) : (
              <>
                <Link to="/login">
                  <Button variant="ghost" size="sm">
                    Sign In
                  </Button>
                </Link>
                <Link to="/register">
                  <Button variant="primary" size="sm">
                    Get Started
                  </Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="pt-14 pb-20 lg:pt-24 lg:pb-28 bg-bg-card border-b border-border-subtle">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            <div className="lg:col-span-7 space-y-6">
              <div>
                <Badge tone="emerald" dot>
                  Commerce Intelligence & Protected PayPal Checkout
                </Badge>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight leading-[1.08] text-text-primary">
                Shop Smarter,{" "}
                <span className="text-[#16A36A]">
                  Authorize Every Dollar Yourself.
                </span>
              </h1>

              <p className="max-w-2xl text-base sm:text-lg text-text-secondary leading-relaxed">
                Describe what you want to buy. PayPilot searches real-time merchant listings, compares prices side by side, enforces your spending limits, and prepares PayPal checkouts that execute strictly after your confirmation.
              </p>

              {/* Search Launch Bar */}
              <form
                onSubmit={handleLaunchPrompt}
                className="flex flex-col sm:flex-row gap-2.5 rounded-xl border border-border-subtle bg-bg-primary p-2 shadow-card max-w-2xl"
              >
                <div className="flex items-center gap-2.5 flex-1 px-2">
                  <Search className="h-4 w-4 text-text-muted shrink-0" />
                  <input
                    type="text"
                    value={heroPrompt}
                    onChange={(e) => setHeroPrompt(e.target.value)}
                    aria-label="Search for a product"
                    className="w-full bg-transparent text-sm text-text-primary placeholder:text-text-muted focus:outline-none py-2"
                    placeholder="Ask PayPilot to find and compare products..."
                  />
                </div>
                <Button type="submit" variant="primary" size="md" icon={<ArrowRight className="h-4 w-4" />}>
                  {isAuthenticated ? "Start Shopping" : "Find Deals"}
                </Button>
              </form>

              <div className="flex flex-wrap items-center gap-6 pt-2 text-xs font-medium text-text-secondary">
                <span className="inline-flex items-center gap-1.5">
                  <Scale className="h-4 w-4 text-[#101828] dark:text-slate-300" />
                  Live Price Comparison
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <ShieldCheck className="h-4 w-4 text-[#16A36A]" />
                  Spending Caps Enforced
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Lock className="h-4 w-4 text-[#16A36A]" />
                  PayPal Verified Checkout
                </span>
              </div>
            </div>

            {/* Hero Right Visual: Clean Commercial Checkout Preview */}
            <div className="lg:col-span-5">
              <Card className="w-full max-w-md mx-auto p-6 space-y-5 shadow-float">
                <div className="flex items-center justify-between">
                  <Badge tone="emerald" dot>
                    Protected Checkout Preview
                  </Badge>
                  <span className="text-xs font-mono text-text-muted">Sample Match</span>
                </div>

                <div className="rounded-xl border border-border-subtle bg-bg-secondary p-4 space-y-2">
                  <p className="text-xs text-text-muted">Top Value Match</p>
                  <h2 className="text-base font-semibold text-text-primary">
                    {scenario.recommendation.name}
                  </h2>
                  <div className="flex items-baseline justify-between pt-1">
                    <span className="text-2xl font-mono font-bold text-text-primary tabular-nums">
                      {scenario.recommendation.price}
                    </span>
                    <span className="text-xs font-semibold text-[#16A36A]">
                      {scenario.recommendation.score}
                    </span>
                  </div>
                </div>

                <div className="space-y-2 text-xs">
                  <div className="flex items-center justify-between rounded-xl border border-border-subtle bg-bg-secondary px-3 py-2.5">
                    <span className="text-text-secondary">Budget & Cap Check</span>
                    <Badge tone="emerald">Within Limit</Badge>
                  </div>
                  <div className="flex items-center justify-between rounded-xl border border-border-subtle bg-bg-secondary px-3 py-2.5">
                    <span className="text-text-secondary">Checkout Gate</span>
                    <Badge tone="slate">Awaiting Buyer Approval</Badge>
                  </div>
                </div>

                <Button
                  variant="emerald"
                  size="md"
                  className="w-full"
                  onClick={() => navigate(isAuthenticated ? "/command-center" : "/register")}
                  icon={<CreditCard className="h-4 w-4" />}
                >
                  {isAuthenticated ? "Open Shopping Assistant" : "Create Free Account"}
                </Button>
              </Card>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-20 border-b border-border-subtle bg-bg-primary">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="max-w-2xl mb-12">
            <Badge tone="slate">Simple Shopping Flow</Badge>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-text-primary">
              From Search Intent to Protected PayPal Checkout
            </h2>
            <p className="mt-2 text-sm text-text-secondary leading-relaxed">
              Every purchase goes through transparent product comparison and automated spending-limit verification before checkout opens.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {WORKFLOW_STEPS.map((item) => {
              const Icon = item.icon;
              return (
                <Card key={item.step} hover className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-[#101828] dark:bg-white/10 text-[#16A36A]">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="text-xs font-mono font-semibold text-text-muted">
                      {item.step}
                    </span>
                  </div>
                  <h3 className="text-base font-semibold text-text-primary">{item.title}</h3>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    {item.description}
                  </p>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* Interactive Comparison Preview */}
      <section id="demo" className="py-20 bg-bg-card border-b border-border-subtle">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-10">
            <div>
              <Badge tone="emerald">Smart Shopping Preview</Badge>
              <h2 className="mt-3 text-3xl font-bold tracking-tight text-text-primary">
                Transparent Recommendations Before You Pay
              </h2>
              <p className="mt-2 text-sm text-text-secondary max-w-2xl">
                Explore how PayPilot evaluates real products, compares offers across merchants, and verifies your limits. Sign in to search live inventory.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_SEARCHES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveScenarioId(item.id)}
                  className={`rounded-lg border px-3.5 py-2 text-xs font-medium transition-colors ${
                    activeScenarioId === item.id
                      ? "border-[#101828] bg-[#101828] text-white dark:border-white dark:bg-white dark:text-[#101828]"
                      : "border-border-subtle bg-bg-card text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <Card className="lg:col-span-7 space-y-4">
              <div className="flex items-center justify-between border-b border-border-subtle pb-3">
                <div className="text-xs font-mono text-text-primary truncate">
                  Query: &ldquo;{scenario.prompt}&rdquo;
                </div>
                <Badge tone="emerald">Sample Output</Badge>
              </div>
              <div className="space-y-3">
                {scenario.stages.map((stage, idx) => (
                  <div
                    key={stage.title}
                    className="flex items-start gap-3 rounded-xl border border-border-subtle bg-bg-secondary p-3.5"
                  >
                    <CheckCircle2 className="h-4 w-4 text-[#12B76A] shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs font-semibold text-text-primary">
                        {idx + 1}. {stage.title}
                      </p>
                      <p className="text-xs text-text-secondary mt-0.5">
                        {stage.detail}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="lg:col-span-5 flex flex-col justify-between space-y-5">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Badge tone="emerald" dot>
                    Recommended Pick
                  </Badge>
                  <span className="text-xs font-mono font-semibold text-[#16A36A]">
                    {scenario.recommendation.score}
                  </span>
                </div>

                <div className="rounded-xl border border-border-subtle bg-bg-secondary p-4 space-y-2">
                  <h3 className="text-base font-semibold text-text-primary">
                    {scenario.recommendation.name}
                  </h3>
                  <p className="text-xs text-text-secondary">
                    Merchant: {scenario.recommendation.merchant}
                  </p>
                  <p className="text-2xl font-mono font-bold text-text-primary pt-1 tabular-nums">
                    {scenario.recommendation.price}
                  </p>
                </div>

                <div className="rounded-xl border border-emerald-200 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10 p-3 text-xs text-[#067647] dark:text-emerald-200 flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 shrink-0 text-[#12B76A]" />
                  <span>
                    Explicit buyer confirmation required — charges happen only after you approve in PayPal.
                  </span>
                </div>
              </div>

              <Link
                to={
                  isAuthenticated
                    ? `/command-center?prompt=${encodeURIComponent(scenario.prompt)}`
                    : "/register"
                }
              >
                <Button variant="primary" size="md" className="w-full" icon={<ChevronRight className="h-4 w-4" />}>
                  Search This Live
                </Button>
              </Link>
            </Card>
          </div>
        </div>
      </section>

      {/* Security & PayPal Checkout */}
      <section id="security" className="py-20 bg-bg-primary">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
          <div className="space-y-5">
            <Badge tone="emerald">Built-in Buyer Protection</Badge>
            <h2 className="text-3xl font-bold tracking-tight text-text-primary">
              Protected PayPal Checkout & Spending Controls
            </h2>
            <p className="text-sm text-text-secondary leading-relaxed">
              Every order amount is verified on our servers, checked against your per-order, daily, and monthly caps, and completed safely through official PayPal checkout.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
              {[
                { icon: Lock, title: "Always Confirm First", desc: "Orders pause for your review before payment begins." },
                { icon: CreditCard, title: "PayPal Checkout", desc: "Supports interactive PayPal buttons and buyer protection." },
                { icon: TrendingUp, title: "Spending Guardrails", desc: "Single-order, daily, and monthly budget limits enforced." },
                { icon: ShoppingBag, title: "Full Receipts", desc: "Every order status and refund is tracked in your ledger." },
              ].map((feat) => {
                const Icon = feat.icon;
                return (
                  <div key={feat.title} className="rounded-xl border border-border-subtle bg-bg-card p-3.5 shadow-card">
                    <Icon className="h-4 w-4 text-[#16A36A] mb-2" />
                    <p className="text-xs font-semibold text-text-primary">{feat.title}</p>
                    <p className="text-xs text-text-secondary mt-1">{feat.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>

          <Card className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-text-primary">
                Account & Payment Safeguards
              </h3>
              <Badge tone="emerald" dot>Active</Badge>
            </div>
            <div className="space-y-3 text-xs">
              <div className="rounded-xl border border-border-subtle bg-bg-secondary p-3.5 flex items-start gap-3">
                <ShieldCheck className="h-4 w-4 text-[#12B76A] shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-text-primary">Server-Verified Pricing</p>
                  <p className="text-text-secondary mt-0.5">
                    Order totals are calculated directly from verified merchant records so prices cannot be altered at checkout.
                  </p>
                </div>
              </div>
              <div className="rounded-xl border border-border-subtle bg-bg-secondary p-3.5 flex items-start gap-3">
                <Lock className="h-4 w-4 text-[#101828] dark:text-slate-200 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-text-primary">Zero Surprise Charges</p>
                  <p className="text-text-secondary mt-0.5">
                    Payments require both your in-app confirmation and explicit PayPal authorization before capture completes.
                  </p>
                </div>
              </div>
              <div className="rounded-xl border border-border-subtle bg-bg-secondary p-3.5 flex items-start gap-3">
                <CheckCircle2 className="h-4 w-4 text-[#16A36A] shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-text-primary">Self-Service Refunds & Tracking</p>
                  <p className="text-text-secondary mt-0.5">
                    Inspect transaction receipts, track PayPal settlement statuses, or request refunds anytime.
                  </p>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border-subtle bg-bg-card py-12">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <PayPilotLogo variant="full" surface="auto" size="sm" />
            <span className="text-xs text-text-secondary">
              Intelligent Product Discovery & Protected PayPal Checkout
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-5 text-xs font-medium text-text-secondary">
            <Link to="/login" className="hover:text-text-primary">Sign In</Link>
            <Link to="/register" className="hover:text-text-primary">Create Account</Link>
            <Link to="/dashboard" className="hover:text-text-primary">Dashboard</Link>
            <Link to="/products" className="hover:text-text-primary">Discover</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
