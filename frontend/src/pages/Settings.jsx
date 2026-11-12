import React, { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Cpu,
  Info,
  Moon,
  RefreshCw,
  Save,
  ShieldCheck,
  Sun,
  User,
} from "lucide-react";
import { PageContainer } from "@/components/layout/MainLayout";
import { PageTransition } from "@/components/animations/PageTransition";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useAuth } from "@/hooks/useAuth";
import { authService } from "@/services/authService";
import { useAppStore } from "@/store/useAppStore";
import { PAYPAL_CLIENT_ID, SUPPORTED_CURRENCIES } from "@/utils/constants";

function renderHealthTone(status) {
  const s = (status || "").toUpperCase();
  if (["OK", "CONFIGURED", "HEALTHY", "CONNECTED"].includes(s)) return "emerald";
  if (["NOT_CONFIGURED", "DEGRADED"].includes(s)) return "amber";
  return "red";
}

export default function Settings() {
  const { user, updateProfile } = useAuth();
  const theme = useAppStore((s) => s.theme);
  const setTheme = useAppStore((s) => s.setTheme);
  const aiPreferences = useAppStore((s) => s.aiPreferences);
  const updateAIPreferences = useAppStore((s) => s.updateAIPreferences);
  const pushToast = useAppStore((s) => s.pushToast);

  const [name, setName] = useState(user?.name || "");
  const [currency, setCurrency] = useState(
    user?.spending_limit?.currency || "USD"
  );
  const [maxSingleTx, setMaxSingleTx] = useState(
    user?.spending_limit?.max_single_transaction ?? ""
  );
  const [dailyLimit, setDailyLimit] = useState(
    user?.spending_limit?.daily_limit ?? ""
  );
  const [monthlyLimit, setMonthlyLimit] = useState(
    user?.spending_limit?.monthly_limit ?? ""
  );
  const [requireManualApproval, setRequireManualApproval] = useState(
    user?.spending_limit?.require_manual_approval ?? true
  );
  const [savingProfile, setSavingProfile] = useState(false);

  useEffect(() => {
    if (!user) return;
    setName(user.name || "");
    if (user.spending_limit) {
      setCurrency(user.spending_limit.currency || "USD");
      setMaxSingleTx(user.spending_limit.max_single_transaction ?? "");
      setDailyLimit(user.spending_limit.daily_limit ?? "");
      setMonthlyLimit(user.spending_limit.monthly_limit ?? "");
      setRequireManualApproval(
        user.spending_limit.require_manual_approval ?? true
      );
    }
  }, [user]);

  const {
    data: healthData,
    isFetching: healthLoading,
    refetch: refetchHealth,
  } = useQuery({
    queryKey: ["backend-health-overview"],
    queryFn: () => authService.getHealthStatus(false),
    staleTime: 30000,
  });

  const handleVerifyLive = async () => {
    await refetchHealth();
    try {
      const [ai, paypal] = await Promise.all([
        authService.getAIHealth(true),
        authService.getPayPalHealth(true),
      ]);
      pushToast({
        title: "Services verified",
        description: `Commerce Engine: ${ai?.status || "checked"} • PayPal: ${
          paypal?.status || "checked"
        }`,
        variant: "info",
      });
    } catch (err) {
      pushToast({
        title: "Verification warning",
        description: err.message,
        variant: "warning",
      });
    }
  };

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setSavingProfile(true);
    try {
      await updateProfile({
        name: name.trim() || undefined,
        currency,
        max_single_transaction: maxSingleTx !== "" ? String(maxSingleTx) : null,
        daily_limit: dailyLimit !== "" ? String(dailyLimit) : null,
        monthly_limit: monthlyLimit !== "" ? String(monthlyLimit) : null,
        require_manual_approval: requireManualApproval,
      });
      pushToast({
        title: "Settings updated",
        description: "Profile and spending guardrails saved cleanly.",
        variant: "success",
      });
    } catch (err) {
      pushToast({
        title: "Update failed",
        description: err.message,
        variant: "error",
      });
    } finally {
      setSavingProfile(false);
    }
  };

  const integrations = healthData?.integrations || {};

  return (
    <PageTransition>
      <PageContainer
        title="Account & Security Settings"
        subtitle="Manage your profile, spending limits, appearance, and connected payment services."
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left 7 cols: Profile + Guardrails */}
          <Card className="lg:col-span-7">
            <CardHeader
              title="Account Profile & Spending Limits"
              subtitle="Saved to your PayPilot account and automatically verified before every order"
              action={<User className="h-4 w-4 text-text-secondary" />}
            />

            <form onSubmit={handleSaveProfile} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full rounded-lg border border-border-subtle bg-bg-secondary px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30 focus:border-[#16A36A]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">
                    Account Email
                  </label>
                  <input
                    type="email"
                    value={user?.email || ""}
                    disabled
                    className="w-full rounded-lg border border-border-subtle bg-bg-secondary px-3 py-2 text-sm text-text-muted cursor-not-allowed opacity-75"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">
                    Guardrail Currency
                  </label>
                  <select
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                    className="w-full rounded-lg border border-border-subtle bg-bg-secondary px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30"
                  >
                    {SUPPORTED_CURRENCIES.map((cur) => (
                      <option key={cur} value={cur}>
                        {cur}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">
                    Max Single Transaction ({currency})
                  </label>
                  <input
                    type="number"
                    min="1"
                    step="0.01"
                    value={maxSingleTx}
                    onChange={(e) => setMaxSingleTx(e.target.value)}
                    placeholder="e.g. 1500"
                    className="w-full rounded-lg border border-border-subtle bg-bg-secondary px-3 py-2 text-sm font-mono text-text-primary focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">
                    Daily Spending Cap ({currency})
                  </label>
                  <input
                    type="number"
                    min="1"
                    step="0.01"
                    value={dailyLimit}
                    onChange={(e) => setDailyLimit(e.target.value)}
                    placeholder="e.g. 3000"
                    className="w-full rounded-lg border border-border-subtle bg-bg-secondary px-3 py-2 text-sm font-mono text-text-primary focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">
                    Monthly Spending Cap ({currency})
                  </label>
                  <input
                    type="number"
                    min="1"
                    step="0.01"
                    value={monthlyLimit}
                    onChange={(e) => setMonthlyLimit(e.target.value)}
                    placeholder="e.g. 10000"
                    className="w-full rounded-lg border border-border-subtle bg-bg-secondary px-3 py-2 text-sm font-mono text-text-primary focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30"
                  />
                </div>
              </div>

              <label className="flex items-start gap-3 rounded-xl border border-border-subtle bg-bg-secondary p-3.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={requireManualApproval}
                  onChange={(e) => setRequireManualApproval(e.target.checked)}
                  className="mt-0.5 rounded border-border-subtle bg-bg-card text-[#16A36A] focus:ring-[#16A36A]/40"
                />
                <div className="text-xs">
                  <p className="font-semibold text-text-primary">
                    Require Confirmation Before Every PayPal Checkout
                  </p>
                  <p className="text-text-secondary mt-0.5">
                    Recommended: pauses every purchase so you can review the item and price before paying.
                  </p>
                </div>
              </label>

              <div className="flex justify-end pt-2">
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  loading={savingProfile}
                  icon={<Save className="h-4 w-4" />}
                >
                  Save Settings
                </Button>
              </div>
            </form>
          </Card>

          {/* Right 5 cols: Theme + Preferences + Service Health */}
          <div className="lg:col-span-5 space-y-6">
            <Card>
              <CardHeader
                title="Appearance & Defaults"
                subtitle="Workspace visual theme and default currency"
              />
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-2.5">
                  <button
                    type="button"
                    onClick={() => setTheme("light")}
                    className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-xs font-medium transition-colors ${
                      theme === "light"
                        ? "border-[#16A36A] bg-emerald-50 dark:bg-emerald-500/15 text-text-primary"
                        : "border-border-subtle bg-bg-secondary text-text-secondary hover:text-text-primary"
                    }`}
                  >
                    <Sun className="h-4 w-4" />
                    Light Mode
                  </button>
                  <button
                    type="button"
                    onClick={() => setTheme("dark")}
                    className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-xs font-medium transition-colors ${
                      theme === "dark"
                        ? "border-[#16A36A] bg-emerald-50 dark:bg-emerald-500/15 text-text-primary"
                        : "border-border-subtle bg-bg-secondary text-text-secondary hover:text-text-primary"
                    }`}
                  >
                    <Moon className="h-4 w-4" />
                    Dark Mode
                  </button>
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">
                    Default Prompt Currency
                  </label>
                  <select
                    value={aiPreferences?.preferredCurrency || "USD"}
                    onChange={(e) =>
                      updateAIPreferences({ preferredCurrency: e.target.value })
                    }
                    className="w-full rounded-lg border border-border-subtle bg-bg-secondary px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-[#16A36A]/30"
                  >
                    {SUPPORTED_CURRENCIES.map((cur) => (
                      <option key={cur} value={cur}>
                        {cur}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </Card>

            {/* Live Connected Services Diagnostics */}
            <Card>
              <CardHeader
                title="Connected Services Health"
                subtitle="Live backend status without synthetic checks"
                action={
                  <Button
                    variant="ghost"
                    size="xs"
                    loading={healthLoading}
                    icon={<RefreshCw className="h-3.5 w-3.5" />}
                    onClick={handleVerifyLive}
                  >
                    Verify
                  </Button>
                }
              />

              <div className="space-y-2.5 text-xs">
                {[
                  { label: "Account Storage", val: integrations.database?.status },
                  { label: "Commerce Engine", val: integrations.ai?.status },
                  { label: "PayPal Checkout", val: integrations.paypal?.status },
                  {
                    label: "Merchant Catalog",
                    val: integrations.product_discovery?.status,
                  },
                ].map((svc) => (
                  <div
                    key={svc.label}
                    className="flex items-center justify-between rounded-xl border border-border-subtle bg-bg-secondary px-3 py-2.5"
                  >
                    <span className="inline-flex items-center gap-2 text-text-primary font-medium">
                      <Cpu className="h-3.5 w-3.5 text-[#16A36A]" />
                      {svc.label}
                    </span>
                    <Badge tone={renderHealthTone(svc.val)}>
                      {svc.val || (healthLoading ? "Checking..." : "Unknown")}
                    </Badge>
                  </div>
                ))}

                <div className="flex items-center justify-between rounded-xl border border-border-subtle bg-bg-secondary px-3 py-2.5">
                  <span className="inline-flex items-center gap-2 text-text-primary font-medium">
                    <ShieldCheck className="h-3.5 w-3.5 text-[#12B76A]" />
                    PayPal Express Buttons
                  </span>
                  <Badge tone={PAYPAL_CLIENT_ID ? "emerald" : "amber"}>
                    {PAYPAL_CLIENT_ID ? "Enabled" : "Standard Redirect Mode"}
                  </Badge>
                </div>
              </div>

              <div className="mt-4 rounded-xl border border-border-subtle bg-bg-secondary p-3 text-[11px] text-text-secondary flex items-start gap-2">
                <Info className="h-4 w-4 shrink-0 text-[#16A36A] mt-0.5" />
                <span>
                  Your spending limits are checked on every order and require your explicit PayPal authorization before any funds move.
                </span>
              </div>
            </Card>
          </div>
        </div>
      </PageContainer>
    </PageTransition>
  );
}
