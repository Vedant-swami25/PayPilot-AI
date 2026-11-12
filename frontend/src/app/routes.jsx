import React from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { MainLayout } from "@/components/layout/MainLayout";
import { PayPilotMark } from "@/components/ui/Logo";

import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import AICommandCenter from "@/pages/AICommandCenter";
import WorkflowHistory from "@/pages/WorkflowHistory";
import ProductDiscovery from "@/pages/ProductDiscovery";
import ProductDetails from "@/pages/ProductDetails";
import ProductComparison from "@/pages/ProductComparison";
import Checkout from "@/pages/Checkout";
import Transactions from "@/pages/Transactions";
import TransactionDetails from "@/pages/TransactionDetails";
import Settings from "@/pages/Settings";
import NotFound from "@/pages/NotFound";

function RouteLoader({ label = "Loading PayPilot..." }) {
  return (
    <div className="min-h-screen bg-bg-primary flex flex-col items-center justify-center gap-3">
      <div className="flex items-center gap-3">
        <PayPilotMark className="h-8 w-8" />
        <Loader2 className="h-4 w-4 animate-spin text-[#16A36A]" />
      </div>
      <p className="text-xs font-medium text-text-secondary">{label}</p>
    </div>
  );
}

export function ProtectedRoute() {
  const { isAuthenticated, isInitializing } = useAuth();
  const location = useLocation();

  if (isInitializing) {
    return <RouteLoader label="Verifying your session..." />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return (
    <MainLayout>
      <Outlet />
    </MainLayout>
  );
}

export function PublicOnlyRoute({ children }) {
  const { isAuthenticated, isInitializing } = useAuth();

  if (isInitializing) {
    return <RouteLoader label="Loading..." />;
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />

      <Route
        path="/login"
        element={
          <PublicOnlyRoute>
            <Login />
          </PublicOnlyRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicOnlyRoute>
            <Register />
          </PublicOnlyRoute>
        }
      />

      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/command-center" element={<AICommandCenter />} />
        <Route path="/workflows" element={<WorkflowHistory />} />
        <Route path="/products" element={<ProductDiscovery />} />
        <Route path="/discovery" element={<ProductDiscovery />} />
        <Route path="/products/:productId" element={<ProductDetails />} />
        <Route path="/compare" element={<ProductComparison />} />
        <Route path="/checkout" element={<Checkout />} />
        <Route path="/checkout/success" element={<Checkout />} />
        <Route path="/checkout/cancel" element={<Checkout />} />
        <Route path="/transactions" element={<Transactions />} />
        <Route path="/transactions/:transactionId" element={<TransactionDetails />} />
        <Route path="/settings" element={<Settings />} />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
