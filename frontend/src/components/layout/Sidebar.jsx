import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  GitCompare,
  LayoutDashboard,
  LogOut,
  Receipt,
  Settings,
  ShoppingBag,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useAppStore } from "@/store/useAppStore";
import { useAuth } from "@/hooks/useAuth";
import { PayPilotLogo } from "@/components/ui/Logo";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/products", label: "Discover", icon: ShoppingBag },
  { to: "/compare", label: "Compare", icon: GitCompare, showCompareBadge: true },
  { to: "/transactions", label: "Transactions", icon: Receipt },
  { to: "/settings", label: "Settings", icon: Settings },
];

function BrandHeader({ collapsed }) {
  return (
    <NavLink
      to="/dashboard"
      className="flex items-center px-1.5 py-1 focus:outline-none"
      aria-label="PayPilot AI Home"
    >
      <PayPilotLogo variant={collapsed ? "symbol" : "full"} size="md" />
    </NavLink>
  );
}

function SidebarNav({ collapsed, onNavigate = null }) {
  const compareCount = useAppStore((s) => s.compareIds.length);

  return (
    <nav className="flex-1 space-y-1 px-3 py-4 overflow-y-auto" aria-label="Main navigation">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={() => onNavigate?.()}
            className={({ isActive }) =>
              `group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150 ${
                isActive
                  ? "bg-[#101828] text-white dark:bg-[#1E293B] dark:text-white shadow-xs"
                  : "text-text-secondary hover:bg-bg-secondary hover:text-text-primary"
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon
                  className={`h-4 w-4 shrink-0 transition-colors ${
                    isActive
                      ? "text-[#16A36A]"
                      : "text-text-muted group-hover:text-text-primary"
                  }`}
                />
                {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
                {!collapsed && item.showCompareBadge && compareCount > 0 && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums ${
                      isActive
                        ? "bg-white/15 text-white"
                        : "bg-[#ECFDF3] text-[#067647] dark:bg-emerald-500/20 dark:text-emerald-300"
                    }`}
                  >
                    {compareCount}
                  </span>
                )}
              </>
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}

function UserProfileFooter({ collapsed, onLogout }) {
  const { user } = useAuth();
  const initials = user?.name?.charAt(0)?.toUpperCase() || "P";

  return (
    <div className="border-t border-border-subtle p-3 space-y-2">
      {!collapsed && user && (
        <div className="flex items-center gap-2.5 rounded-lg bg-bg-secondary px-2.5 py-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#101828] text-xs font-semibold text-white dark:bg-[#16A36A]">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-text-primary truncate leading-tight">
              {user.name || "Account"}
            </p>
            <p className="text-[11px] text-text-muted truncate mt-0.5 leading-tight">
              {user.email || ""}
            </p>
          </div>
        </div>
      )}
      <button
        type="button"
        onClick={onLogout}
        className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-text-secondary hover:bg-[#FEF3F2] hover:text-[#D92D20] dark:hover:bg-rose-500/10 dark:hover:text-rose-400 transition-colors"
      >
        <LogOut className="h-4 w-4 shrink-0" />
        {!collapsed && <span>Sign Out</span>}
      </button>
    </div>
  );
}

export function Sidebar() {
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const setCollapsed = useAppStore((s) => s.setSidebarCollapsed);
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <aside
      className={`hidden lg:flex flex-col shrink-0 border-r border-border-subtle bg-bg-card transition-all duration-200 ${
        collapsed ? "w-[74px]" : "w-64"
      }`}
    >
      <div className="flex h-16 items-center justify-between border-b border-border-subtle px-3">
        <BrandHeader collapsed={collapsed} />
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="rounded-lg p-1.5 text-text-muted hover:bg-bg-secondary hover:text-text-primary"
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>

      <SidebarNav collapsed={collapsed} />
      <UserProfileFooter collapsed={collapsed} onLogout={handleLogout} />
    </aside>
  );
}

export function MobileNavigation() {
  const open = useAppStore((s) => s.mobileNavOpen);
  const setOpen = useAppStore((s) => s.setMobileNavOpen);
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    setOpen(false);
    await logout();
    navigate("/login");
  };

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
            className="fixed inset-0 bg-[#101828]/45"
          />
          <motion.aside
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ type: "spring", stiffness: 340, damping: 34 }}
            className="relative z-10 flex h-full w-72 flex-col bg-bg-card border-r border-border-subtle"
          >
            <div className="flex h-16 items-center justify-between border-b border-border-subtle px-4">
              <BrandHeader collapsed={false} />
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close navigation menu"
                className="rounded-lg p-1.5 text-text-secondary hover:bg-bg-secondary"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <SidebarNav collapsed={false} onNavigate={() => setOpen(false)} />
            <UserProfileFooter collapsed={false} onLogout={handleLogout} />
          </motion.aside>
        </div>
      )}
    </AnimatePresence>
  );
}
