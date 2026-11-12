import { apiClient } from "./api";

export const paymentService = {
  async getQuote({ productId, quantity = 1, displayCurrency = null }) {
    const params = { product_id: productId, quantity };
    if (displayCurrency) {
      params.display_currency = displayCurrency;
    }
    const { data } = await apiClient.get("/api/v1/payments/quote", { params });
    return data;
  },

  async createOrder({
    workflowId = null,
    productId = null,
    quantity = 1,
    expectedAmount = null,
    expectedCurrency = null,
    displayCurrency = null,
    returnUrl = `${window.location.origin}/checkout/success`,
    cancelUrl = `${window.location.origin}/checkout/cancel`,
    idempotencyKey = null,
  }) {
    const { data } = await apiClient.post("/api/v1/payments/create-order", {
      workflow_id: workflowId,
      product_id: productId,
      quantity,
      expected_amount: expectedAmount ? String(expectedAmount) : null,
      expected_currency: expectedCurrency || null,
      display_currency: displayCurrency || null,
      return_url: returnUrl,
      cancel_url: cancelUrl,
      idempotency_key: idempotencyKey,
    });
    return data;
  },

  async getPayment(paymentId, { sync = true } = {}) {
    const { data } = await apiClient.get(`/api/v1/payments/${paymentId}`, {
      params: { sync },
    });
    return data;
  },

  async capturePayment(paymentId) {
    const { data } = await apiClient.post(
      `/api/v1/payments/${paymentId}/capture`,
      { confirm_capture: true }
    );
    return data;
  },

  async cancelPayment(paymentId, reason = "Cancelled by user") {
    const { data } = await apiClient.post(
      `/api/v1/payments/${paymentId}/cancel`,
      { reason }
    );
    return data;
  },

  async refundPayment(paymentId, reason = "Requested by user") {
    const { data } = await apiClient.post(
      `/api/v1/payments/${paymentId}/refund`,
      { reason }
    );
    return data;
  },
};

