import { useContext } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CommerceContext } from "@/context/CommerceContext";
import { commerceService } from "@/services/commerceService";
import { productService } from "@/services/productService";
import { useAppStore } from "@/store/useAppStore";

export function useCommerce() {
  const ctx = useContext(CommerceContext);
  if (!ctx) {
    throw new Error("useCommerce must be used inside CommerceProvider");
  }
  return ctx;
}

export function useCommerceHistory({ limit = 20, offset = 0, enabled = true } = {}) {
  return useQuery({
    queryKey: ["commerce-history", { limit, offset }],
    queryFn: () => commerceService.getHistory({ limit, offset }),
    enabled,
    staleTime: 15000,
  });
}

export function useWorkflow(workflowId, { enabled = true } = {}) {
  return useQuery({
    queryKey: ["workflow", workflowId],
    queryFn: () => commerceService.getWorkflow(workflowId),
    enabled: Boolean(workflowId) && enabled,
    refetchInterval: (query) => {
      const st = query.state.data?.status;
      return st === "RUNNING" || st === "PENDING" ? 2500 : false;
    },
  });
}

export function useSubmitCommerceRequest() {
  const queryClient = useQueryClient();
  const pushToast = useAppStore((s) => s.pushToast);
  const addRecentCommand = useAppStore((s) => s.addRecentCommand);
  const setActiveWorkflowId = useAppStore((s) => s.setActiveWorkflowId);

  return useMutation({
    mutationFn: (payload) => commerceService.submitRequest(payload),
    onSuccess: (workflow, variables) => {
      addRecentCommand(variables.requestText);
      setActiveWorkflowId(workflow.id);
      queryClient.setQueryData(["workflow", workflow.id], workflow);
      queryClient.invalidateQueries({ queryKey: ["commerce-history"] });
    },
    onError: (err) => {
      pushToast({
        title: "Search request failed",
        description: err.message,
        variant: "error",
      });
    },
  });
}

export function useApproveWorkflow() {
  const queryClient = useQueryClient();
  const pushToast = useAppStore((s) => s.pushToast);

  return useMutation({
    mutationFn: ({ workflowId, ...options }) =>
      commerceService.approveWorkflow(workflowId, options),
    onSuccess: (data) => {
      if (data?.workflow?.id) {
        queryClient.setQueryData(["workflow", data.workflow.id], data.workflow);
      }
      queryClient.invalidateQueries({ queryKey: ["commerce-history"] });
      pushToast({
        title: "Purchase confirmed",
        description: data?.payment_order
          ? "PayPal checkout order created and ready for your payment."
          : "Order confirmation recorded.",
        variant: "success",
      });
    },
    onError: (err) => {
      pushToast({
        title: "Approval error",
        description: err.message,
        variant: "error",
      });
    },
  });
}

export function useProductSearch(params, { enabled = false } = {}) {
  return useQuery({
    queryKey: ["product-search", params],
    queryFn: () => productService.searchProducts(params),
    enabled: Boolean(params?.query?.trim()) && enabled,
    staleTime: 60000,
  });
}

export function useCancelWorkflow() {
  const queryClient = useQueryClient();
  const pushToast = useAppStore((s) => s.pushToast);

  return useMutation({
    mutationFn: (workflowId) => commerceService.cancelWorkflow(workflowId),
    onSuccess: (workflow) => {
      queryClient.invalidateQueries({ queryKey: ["workflow", workflow.id] });
      queryClient.invalidateQueries({ queryKey: ["commerce-history"] });
      pushToast({
        title: "Search cancelled",
        description: "The active shopping session has been stopped.",
        variant: "info",
      });
    },
    onError: (err) => {
      pushToast({
        title: "Cancellation failed",
        description: err.message,
        variant: "error",
      });
    },
  });
}

export function useProductDetails(productId, { currency = null, enabled = true } = {}) {
  return useQuery({
    queryKey: ["product", productId, currency],
    queryFn: () => productService.getProduct(productId, currency),
    enabled: Boolean(productId) && enabled,
  });
}

