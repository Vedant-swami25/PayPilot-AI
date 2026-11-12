import React from "react";
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { PayPilotMark } from "@/components/ui/Logo";
import { useAuth } from "@/hooks/useAuth";

export default function NotFound() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen bg-bg-primary text-text-primary flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center space-y-6">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-border-subtle bg-bg-card shadow-card">
          <PayPilotMark className="h-9 w-9" />
        </div>
        <div className="space-y-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border-subtle bg-bg-card px-3 py-1 text-xs font-mono text-text-secondary">
            404 • Page Not Found
          </span>
          <h1 className="text-3xl font-bold tracking-tight text-text-primary">
            We couldn&apos;t find that page
          </h1>
          <p className="text-sm text-text-secondary">
            The requested page does not exist or may have moved.
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link to={isAuthenticated ? "/dashboard" : "/"}>
            <Button variant="primary" size="md" icon={<ArrowLeft className="h-4 w-4" />}>
              {isAuthenticated ? "Return to Dashboard" : "Back to Home"}
            </Button>
          </Link>
          {isAuthenticated && (
            <Link to="/products">
              <Button variant="outline" size="md">
                Browse Products
              </Button>
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
