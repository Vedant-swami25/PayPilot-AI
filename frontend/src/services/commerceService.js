import { apiClient } from "./api";

export const commerceService = {
  async submitRequest({
    requestText,
    budget = null,
    currency = null,
    quantity = 1,
    idempotencyKey = null,
  }) {
    const { data } = await apiClient.post(
      "/api/v1/commerce/request",
      {
        request_text: requestText,
        budget: budget ? String(budget) : null,
        currency: currency || null,
        quantity,
        idempotency_key: idempotencyKey,
      },
      { timeout: 150000 }
    );
    return data;
  },

  async getWorkflow(workflowId) {
    const { data } = await apiClient.get(
      `/api/v1/commerce/workflows/${workflowId}`
    );
    return data;
  },

  async getHistory({ limit = 20, offset = 0 } = {}) {
    const { data } = await apiClient.get("/api/v1/commerce/history", {
      params: { limit, offset },
    });
    return data;
  },

  async approveWorkflow(
    workflowId,
    {
      productId = null,
      quantity = 1,
      confirmPurchase = true,
      createPaypalOrder = true,
      returnUrl = `${window.location.origin}/checkout/success?workflowId=${encodeURIComponent(workflowId)}`,
      cancelUrl = `${window.location.origin}/checkout/cancel?workflowId=${encodeURIComponent(workflowId)}`,
    } = {}
  ) {
    const { data } = await apiClient.post(
      `/api/v1/commerce/workflows/${workflowId}/approve`,
      {
        product_id: productId,
        quantity,
        confirm_purchase: confirmPurchase,
        create_paypal_order: createPaypalOrder,
        return_url: returnUrl,
        cancel_url: cancelUrl,
      }
    );
    return data;
  },

  async cancelWorkflow(workflowId) {
    const { data } = await apiClient.post(`/api/v1/agents/cancel/${workflowId}`);
    return data;
  },
};

