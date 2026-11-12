import { apiClient, tokenVault } from "./api";

export const authService = {
  async register({ name, email, password }) {
    const { data } = await apiClient.post("/api/v1/auth/register", {
      name,
      email,
      password,
    });
    tokenVault.setTokens(
      {
        accessToken: data.tokens.access_token,
        refreshToken: data.tokens.refresh_token,
      },
      false
    );
    return data;
  },

  async login({ email, password, rememberMe = false }) {
    const { data } = await apiClient.post("/api/v1/auth/login", {
      email,
      password,
    });
    tokenVault.setTokens(
      {
        accessToken: data.tokens.access_token,
        refreshToken: data.tokens.refresh_token,
      },
      rememberMe
    );
    return data;
  },

  async logout() {
    const refreshToken = tokenVault.getRefreshToken();
    try {
      await apiClient.post("/api/v1/auth/logout", {
        refresh_token: refreshToken || null,
      });
    } finally {
      tokenVault.clear();
    }
  },

  async getMe() {
    const { data } = await apiClient.get("/api/v1/auth/me");
    return data;
  },

  async updateProfile(payload) {
    const { data } = await apiClient.put("/api/v1/auth/me", payload);
    return data;
  },

  async getHealthStatus(verify = false) {
    const { data } = await apiClient.get("/api/v1/health", {
      params: { verify },
      timeout: 8000,
    });
    return data;
  },

  async getAIHealth(verify = false) {
    const { data } = await apiClient.get("/api/v1/health/ai", {
      params: { verify },
      timeout: 8000,
    });
    return data;
  },

  async getPayPalHealth(verify = false) {
    const { data } = await apiClient.get("/api/v1/health/paypal", {
      params: { verify },
      timeout: 8000,
    });
    return data;
  },
};

