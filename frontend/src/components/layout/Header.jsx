import React, { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Bell,
  LogOut,
  Menu,
  Moon,
  Search,
  Settings,
  ShieldCheck,
  Sun,
  User as UserIcon,
} from "lucide-react";
import { useAppStore } from "@/store/useAppStore";
import { useAuth } from "@/hooks/useAuth";
import { useCommerceHistory } from "@/hooks/useCommerce";
import { Dropdown } from "@/components/ui/Toast";
import { ShoppingStatusBadge } from "@/components/commerce/ShoppingStatus";
import { formatRelativeTime } from "@/utils/formatDate";

function resolvePageTitle(pathname) {
  if (pathname.startsWith("/dashboard")) return "Dashboard";
  if (pathname.startsWith("/command-center")) return "Shopping Assistant";
  if (pathname.startsWith("/workflows")) return "Shopping History";
  if (pathname.startsWith("/products/")) return "Product Details";
  if (pathname.startsWith("/products") || pathname.startsWith("/discovery")) return "Discover";
  if (pathname.startsWith("/compare")) return "Compare";
  if (pathname.startsWith("/checkout")) return "Checkout";
  if (pathname.startsWith("/transactions/")) return "Transaction Receipt";
  if (pathname.startsWith("/transactions")) return "Transactions";
  if (pathname.startsWith("/settings")) return "Settings";
  return "PayPilot";
}

export function Header() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const theme = useAppStore((s) => s.theme);
  const toggleTheme = useAppStore((s) => s.toggleTheme);
  const setMobileNavOpen = useAppStore((s) => s.setMobileNavOpen);

  const [searchValue, setSearchValue] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);

  const { data: historyData } = useCommerceHistory({
    limit: 5,
    enabled: Boolean(user),
  });
  const recentSessions = historyData?.workflows || [];
  const pageTitle = resolvePageTitle(location.pathname);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    const q = searchValue.trim();
    if (!q) return;
    navigate(`/products?query=${encodeURIComponent(q)}`);
    setSearchValue("");
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b border-border-subtle bg-bg-card px-4 sm:px-6">
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <button
          type="button"
          onClick={() => setMobileNavOpen(true)}
          aria-label="Open menu"
          className="rounded-lg border border-border-subtle p-2 text-text-secondary hover:bg-bg-secondary hover:text-text-primary lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>

        <span className="text-sm font-semibold text-text-primary shrink-0">
          {pageTitle}
        </span>

        <form
          onSubmit={handleSearchSubmit}
          className="relative flex-1 max-w-md hidden md:block ml-3"
        >
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <input
            type="search"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            placeholder="Search products..."
            aria-label="Search products"
            className="w-full rounded-lg border border-border-subtle bg-bg-primary py-1.5 pl-9 pr-3 text-sm text-text-primary placeholder:text-text-muted focus:border-[#16A36A] focus:outline-none focus:ring-2 focus:ring-[#16A36A]/15"
          />
        </form>
      </div>

      <div className="flex items-center gap-2 sm:gap-2.5">
        <button
          type="button"
          onClick={toggleTheme}
          aria-label="Toggle theme"
          className="rounded-lg border border-border-subtle bg-bg-card p-2 text-text-secondary hover:bg-bg-secondary hover:text-text-primary transition-colors"
        >
          {theme === "dark" ? (
            <Sun className="h-4 w-4 text-amber-400" />
          ) : (
            <Moon className="h-4 w-4 text-[#344054]" />
          )}
        </button>

        {/* Notifications driven by real shopping session activity */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setNotifOpen((v) => !v)}
            aria-label="Recent shopping notifications"
            className="relative rounded-lg border border-border-subtle bg-bg-card p-2 text-text-secondary hover:bg-bg-secondary hover:text-text-primary transition-colors"
          >
            <Bell className="h-4 w-4" />
            {recentSessions.length > 0 && (
              <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-[#16A36A]" />
            )}
          </button>

          {notifOpen && (
            <>
              <div
                className="fixed inset-0 z-30"
                onClick={() => setNotifOpen(false)}
              />
              <div className="absolute right-0 z-40 mt-2 w-80 rounded-xl border border-border-subtle bg-bg-card p-3 shadow-elevated">
                <div className="flex items-center justify-between px-1 pb-2 border-b border-border-subtle">
                  <span className="text-xs font-semibold text-text-primary">
                    Recent Activity
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setNotifOpen(false);
                      navigate("/workflows");
                    }}
                    className="text-[11px] font-medium text-[#16A36A] hover:underline"
                  >
                    View History
                  </button>
                </div>
                <div className="mt-2 max-h-64 overflow-y-auto space-y-2">
                  {recentSessions.length === 0 ? (
                    <p className="py-4 text-center text-xs text-text-muted">
                      No recent shopping activity yet.
                    </p>
                  ) : (
                    recentSessions.map((session) => (
                      <button
                        key={session.id}
                        type="button"
                        onClick={() => {
                          setNotifOpen(false);
                          navigate(`/command-center?workflowId=${session.id}`);
                        }}
                        className="w-full text-left rounded-lg border border-border-subtle bg-bg-primary p-2.5 text-xs hover:border-border-strong transition-colors"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <ShoppingStatusBadge status={session.status} />
                          <span className="text-[10px] text-text-muted">
                            {formatRelativeTime(session.created_at)}
                          </span>
                        </div>
                        <p className="mt-1.5 text-text-primary font-medium line-clamp-1">
                          {session.request_text}
                        </p>
                      </button>
                    ))
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        <Dropdown
          align="right"
          trigger={
            <button
              type="button"
              className="flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-card px-2.5 py-1.5 hover:bg-bg-secondary transition-colors"
            >
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[#101828] text-xs font-semibold text-white dark:bg-[#16A36A]">
                {user?.name?.charAt(0)?.toUpperCase() || "P"}
              </div>
              <div className="hidden md:block text-left">
                <p className="text-xs font-semibold text-text-primary leading-none">
                  {user?.name || "Account"}
                </p>
                <p className="text-[11px] text-text-muted mt-0.5 leading-none">
                  {user?.email || ""}
                </p>
              </div>
            </button>
          }
          items={[
            {
              label: "Spending Limits & Profile",
              icon: <UserIcon className="h-3.5 w-3.5" />,
              onClick: () => navigate("/settings"),
            },
            {
              label: "Shopping History",
              icon: <ShieldCheck className="h-3.5 w-3.5" />,
              onClick: () => navigate("/workflows"),
            },
            {
              label: "Settings",
              icon: <Settings className="h-3.5 w-3.5" />,
              onClick: () => navigate("/settings"),
            },
            { divider: true },
            {
              label: "Sign Out",
              icon: <LogOut className="h-3.5 w-3.5" />,
              danger: true,
              onClick: async () => {
                await logout();
                navigate("/login");
              },
            },
          ]}
        />
      </div>
    </header>
  );
}
