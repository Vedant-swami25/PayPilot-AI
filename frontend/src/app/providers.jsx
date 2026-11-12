import React from "react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { AuthProvider } from "@/context/AuthContext";
import { CommerceProvider } from "@/context/CommerceContext";

export function createAppQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
    },
  });
}

const defaultQueryClient = createAppQueryClient();

export function AppProviders({
  children,
  queryClient = defaultQueryClient,
  useRouter = true,
}) {
  const tree = (
    <MotionConfig reducedMotion="user">
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <CommerceProvider>{children}</CommerceProvider>
        </AuthProvider>
      </QueryClientProvider>
    </MotionConfig>
  );

  return useRouter ? <BrowserRouter>{tree}</BrowserRouter> : tree;
}

