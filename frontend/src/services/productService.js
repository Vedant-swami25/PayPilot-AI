import { apiClient } from "./api";

export const productService = {
  async searchProducts({ query, maxPrice = null, currency = "USD", limit = 12 }) {
    const params = { query, currency, limit };
    if (maxPrice !== null && maxPrice !== "" && Number(maxPrice) > 0) {
      params.max_price = String(maxPrice);
    }
    const { data } = await apiClient.get("/api/v1/products/search", { params });
    return data;
  },

  async getProduct(productId, currency = null) {
    const params = currency ? { currency } : undefined;
    const { data } = await apiClient.get(`/api/v1/products/${productId}`, {
      params,
    });
    return data;
  },

  async compareProducts({
    productIds,
    budget = null,
    currency = "USD",
    requirements = [],
  }) {
    const { data } = await apiClient.post("/api/v1/products/compare", {
      product_ids: productIds,
      budget: budget ? String(budget) : null,
      currency,
      requirements,
    });
    return data;
  },
};

