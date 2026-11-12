import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Info, Lock, Mail, ArrowRight } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PayPilotLogo } from "@/components/ui/Logo";
import { useAppStore } from "@/store/useAppStore";

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const pushToast = useAppStore((s) => s.pushToast);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showResetNote, setShowResetNote] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const redirectTo = location.state?.from?.pathname || "/dashboard";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage("");

    if (!email.trim() || !password) {
      setErrorMessage("Please enter your email address and password.");
      return;
    }

    setLoading(true);
    try {
      await login({ email: email.trim(), password, rememberMe });
      pushToast({
        title: "Welcome back to PayPilot AI",
        description: "Your shopping workspace is ready.",
        variant: "success",
      });
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setErrorMessage(
        err?.message || "Sign in failed. Please check your credentials."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg-primary text-text-primary flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md space-y-6">
        <div className="flex flex-col items-center text-center space-y-3">
          <Link to="/" className="inline-flex items-center">
            <PayPilotLogo variant="full" surface="auto" size="md" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-text-primary">
              Sign in to PayPilot AI
            </h1>
            <p className="text-xs text-text-secondary mt-1">
              Access your saved searches, spending limits, and PayPal orders
            </p>
          </div>
        </div>

        <Card className="p-6 shadow-card">
          <form onSubmit={handleSubmit} className="space-y-4">
            {errorMessage && (
              <div
                role="alert"
                className="rounded-xl border border-rose-200 bg-rose-50 dark:border-rose-500/35 dark:bg-rose-500/10 p-3 text-xs text-[#B42318] dark:text-rose-300"
              >
                {errorMessage}
              </div>
            )}

            <div className="space-y-1.5">
              <label
                htmlFor="login-email"
                className="block text-xs font-medium text-text-secondary"
              >
                Email Address
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
                <input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="w-full rounded-lg border border-border-subtle bg-bg-secondary pl-10 pr-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30 focus:border-[#16A36A]"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="login-password"
                  className="block text-xs font-medium text-text-secondary"
                >
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => setShowResetNote((v) => !v)}
                  className="text-[11px] font-medium text-[#16A36A] hover:underline"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
                <input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full rounded-lg border border-border-subtle bg-bg-secondary pl-10 pr-10 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30 focus:border-[#16A36A]"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            {showResetNote && (
              <div className="rounded-xl border border-border-subtle bg-bg-secondary p-3 text-[11px] text-text-secondary flex items-start gap-2">
                <Info className="h-4 w-4 shrink-0 text-[#101828] dark:text-slate-300 mt-0.5" />
                <span>
                  Self-service password recovery is not currently exposed by the backend authentication API. Contact your administrator or register a new workspace account.
                </span>
              </div>
            )}

            <label className="flex items-center gap-2 text-xs text-text-secondary cursor-pointer select-none">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="rounded border-border-subtle bg-bg-secondary text-[#16A36A] focus:ring-[#16A36A]/40"
              />
              <span>Keep access session across browser restarts</span>
            </label>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading}
              className="w-full"
              icon={<ArrowRight className="h-4 w-4" />}
            >
              Sign In
            </Button>
          </form>
        </Card>

        <p className="text-center text-xs text-text-secondary">
          New to PayPilot AI?{" "}
          <Link to="/register" className="font-semibold text-[#16A36A] hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}
