import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { paymentService } from "@/services/paymentService";
import { transactionService } from "@/services/transactionService";
import { useAppStore } from "@/store/useAppStore";

export function useCheckoutQuote(
  { productId, quantity = 1, displayCurrency = null },
  { enabled = true } = {}
) {
  return useQuery({
    queryKey: ["checkout-quote", productId, quantity, displayCurrency],
    queryFn: () =>
      paymentService.getQuote({ productId, quantity, displayCurrency }),
    enabled: Boolean(productId) && enabled,
    staleTime: 30000,
  });
}

export function usePaymentOrder(paymentId, { sync = true, enabled = true } = {}) {
  return useQuery({
    queryKey: ["payment-order", paymentId, sync],
    queryFn: () => paymentService.getPayment(paymentId, { sync }),
    enabled: Boolean(paymentId) && enabled,
  });
}

export function useCreateOrder() {
  const queryClient = useQueryClient();
  const pushToast = useAppStore((s) => s.pushToast);

  return useMutation({
    mutationFn: (payload) => paymentService.createOrder(payload),
    onSuccess: (order) => {
      queryClient.setQueryData(["payment-order", order.id, true], order);
      queryClient.invalidateQueries({ queryKey: ["commerce-history"] });
    },
    onError: (err) => {
      pushToast({
        title: "Order creation failed",
        description: err.message,
        variant: "error",
      });
    },
  });
}

export function useCapturePayment() {
  const queryClient = useQueryClient();
  const pushToast = useAppStore((s) => s.pushToast);

  return useMutation({
    mutationFn: (paymentId) => paymentService.capturePayment(paymentId),
    onSuccess: (order) => {
      queryClient.setQueryData(["payment-order", order.id, true], order);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["transaction-summary"] });
      queryClient.invalidateQueries({ queryKey: ["commerce-history"] });
    },
    onError: (err) => {
      pushToast({
        title: "Payment capture failed",
        description: err.message,
        variant: "error",
      });
    },
  });
}

export function useCancelPayment() {
  const queryClient = useQueryClient();
  const pushToast = useAppStore((s) => s.pushToast);

  return useMutation({
    mutationFn: ({ paymentId, reason }) =>
      paymentService.cancelPayment(paymentId, reason),
    onSuccess: (order) => {
      queryClient.setQueryData(["payment-order", order.id, true], order);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["transaction-summary"] });
      pushToast({
        title: "Order cancelled",
        description: "Payment order was cancelled before capture.",
        variant: "info",
      });
    },
    onError: (err) => {
      pushToast({
        title: "Unable to cancel order",
        description: err.message,
        variant: "error",
      });
    },
  });
}

export function useRefundPayment() {
  const queryClient = useQueryClient();
  const pushToast = useAppStore((s) => s.pushToast);

  return useMutation({
    mutationFn: ({ paymentId, reason }) =>
      paymentService.refundPayment(paymentId, reason),
    onSuccess: (order) => {
      queryClient.setQueryData(["payment-order", order.id, false], order);
      queryClient.setQueryData(["payment-order", order.id, true], order);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["transaction"] });
      queryClient.invalidateQueries({ queryKey: ["transaction-summary"] });
      pushToast({
        title: "Refund processed",
        description: "PayPal Sandbox capture has been refunded.",
        variant: "success",
      });
    },
    onError: (err) => {
      pushToast({
        title: "Refund failed",
        description: err.message,
        variant: "error",
      });
    },
  });
}

export function useTransactions({ status = null, limit = 50, enabled = true } = {}) {
  return useQuery({
    queryKey: ["transactions", { status, limit }],
    queryFn: () => transactionService.listTransactions({ status, limit }),
    enabled,
    staleTime: 15000,
  });
}

export function useTransactionSummary({ enabled = true } = {}) {
  return useQuery({
    queryKey: ["transaction-summary"],
    queryFn: () => transactionService.getSummary(),
    enabled,
    staleTime: 15000,
  });
}

export function useTransactionDetails(transactionId) {
  return useQuery({
    queryKey: ["transaction", transactionId],
    queryFn: () => transactionService.getTransaction(transactionId),
    enabled: Boolean(transactionId),
  });
}

