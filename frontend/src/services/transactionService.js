import { apiClient } from "./api";

export const transactionService = {
  async listTransactions({ status = null, limit = 50, offset = 0 } = {}) {
    const params = { limit, offset };
    if (status && status !== "ALL") {
      params.status = status;
    }
    const { data } = await apiClient.get("/api/v1/transactions", { params });
    return data;
  },

  async getSummary() {
    const { data } = await apiClient.get("/api/v1/transactions/summary");
    return data;
  },

  async getTransaction(transactionId) {
    const { data } = await apiClient.get(
      `/api/v1/transactions/${transactionId}`
    );
    return data;
  },
};

