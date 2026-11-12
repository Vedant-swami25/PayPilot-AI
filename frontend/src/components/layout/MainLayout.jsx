import React from "react";
import { Header } from "./Header";
import { MobileNavigation, Sidebar } from "./Sidebar";

export function PageContainer({
  title,
  subtitle = null,
  action = null,
  children,
  className = "",
}) {
  return (
    <div className={`mx-auto w-full max-w-[1360px] px-4 sm:px-6 lg:px-8 py-6 ${className}`}>
      {(title || action) && (
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            {title && (
              <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-text-primary">
                {title}
              </h1>
            )}
            {subtitle && (
              <p className="mt-1 text-sm text-text-secondary">{subtitle}</p>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

export function MainLayout({ children }) {
  return (
    <div className="flex min-h-screen bg-bg-primary text-text-primary">
      <Sidebar />
      <MobileNavigation />
      <div className="flex flex-1 flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-x-hidden">{children}</main>
      </div>
    </div>
  );
}

