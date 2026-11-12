import React, { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, Eye, EyeOff, Lock, Mail, User } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PayPilotLogo } from "@/components/ui/Logo";
import { useAppStore } from "@/store/useAppStore";

function evaluatePasswordStrength(pwd) {
  if (!pwd) return { score: 0, label: "", color: "bg-slate-200 dark:bg-slate-700" };
  let score = 0;
  if (pwd.length >= 8) score += 1;
  if (/[A-Z]/.test(pwd) && /[a-z]/.test(pwd)) score += 1;
  if (/\d/.test(pwd)) score += 1;
  if (/[^A-Za-z0-9]/.test(pwd) && pwd.length >= 10) score += 1;

  const map = [
    { label: "Too short (min 8 chars)", color: "bg-[#D92D20]" },
    { label: "Weak", color: "bg-[#D92D20]" },
    { label: "Fair", color: "bg-amber-500" },
    { label: "Strong", color: "bg-[#101828] dark:bg-emerald-500" },
    { label: "Excellent", color: "bg-[#16A36A]" },
  ];
  return { score, ...map[score] };
}

export default function Register() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { register } = useAuth();
  const pushToast = useAppStore((s) => s.pushToast);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const strength = useMemo(() => evaluatePasswordStrength(password), [password]);
  const initialPrompt = searchParams.get("prompt");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage("");

    if (!name.trim() || name.trim().length < 2) {
      setErrorMessage("Please enter your full name (at least 2 characters).");
      return;
    }
    if (!email.trim()) {
      setErrorMessage("Please enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setErrorMessage("Password must be at least 8 characters long.");
      return;
    }
    if (!/[a-z]/.test(password) || !/[A-Z]/.test(password) || !/\d/.test(password)) {
      setErrorMessage(
        "Password must include at least one uppercase letter, one lowercase letter, and one digit."
      );
      return;
    }
    if (password !== confirmPassword) {
      setErrorMessage("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await register({
        name: name.trim(),
        email: email.trim(),
        password,
      });
      pushToast({
        title: "Account created",
        description: "Your PayPilot workspace and default limits are ready.",
        variant: "success",
      });
      if (initialPrompt) {
        navigate(`/command-center?prompt=${encodeURIComponent(initialPrompt)}`, {
          replace: true,
        });
      } else {
        navigate("/dashboard", { replace: true });
      }
    } catch (err) {
      setErrorMessage(err?.message || "Registration failed. Please try again.");
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
              Create your PayPilot Account
            </h1>
            <p className="text-xs text-text-secondary mt-1">
              Smart product comparison with built-in spending protection
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
                htmlFor="reg-name"
                className="block text-xs font-medium text-text-secondary"
              >
                Full Name
              </label>
              <div className="relative">
                <User className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
                <input
                  id="reg-name"
                  type="text"
                  autoComplete="name"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Alex Rivera"
                  className="w-full rounded-lg border border-border-subtle bg-bg-secondary pl-10 pr-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30 focus:border-[#16A36A]"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="reg-email"
                className="block text-xs font-medium text-text-secondary"
              >
                Email Address
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
                <input
                  id="reg-email"
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
              <label
                htmlFor="reg-password"
                className="block text-xs font-medium text-text-secondary"
              >
                Password
              </label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
                <input
                  id="reg-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
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
              {password && (
                <div className="space-y-1 pt-1">
                  <div className="grid grid-cols-4 gap-1">
                    {[1, 2, 3, 4].map((step) => (
                      <div
                        key={step}
                        className={`h-1 rounded-full transition-colors ${
                          strength.score >= step
                            ? strength.color
                            : "bg-slate-200 dark:bg-slate-700"
                        }`}
                      />
                    ))}
                  </div>
                  <p className="text-[11px] text-text-secondary">{strength.label}</p>
                </div>
              )}
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="reg-confirm"
                className="block text-xs font-medium text-text-secondary"
              >
                Confirm Password
              </label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
                <input
                  id="reg-confirm"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter password"
                  className="w-full rounded-lg border border-border-subtle bg-bg-secondary pl-10 pr-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30 focus:border-[#16A36A]"
                />
              </div>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading}
              className="w-full"
              icon={<ArrowRight className="h-4 w-4" />}
            >
              Create Account
            </Button>
          </form>
        </Card>

        <p className="text-center text-xs text-text-secondary">
          Already have an account?{" "}
          <Link to="/login" className="font-semibold text-[#16A36A] hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
