import axios from "axios";
import { API_BASE_URL } from "@/utils/constants";

const ACCESS_STORAGE_KEY = "paypilot_access_token";
const REMEMBER_ME_KEY = "paypilot_remember_me";

// Keep refresh token strictly in memory — NEVER in localStorage
let memoryAccessToken = null;
let memoryRefreshToken = null;
let sessionExpiredHandler = null;
let refreshInFlight = null;

export class ApiError extends Error {
  constructor({ status, code, message, details = null }) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function normalizeApiError(error) {
  if (error instanceof ApiError) return error;

  if (!error.response) {
    if (error.code === "ECONNABORTED") {
      return new ApiError({
        status: 408,
        code: "REQUEST_TIMEOUT",
        message: "The request timed out. Please try again.",
      });
    }
    return new ApiError({
      status: 0,
      code: "NETWORK_ERROR",
      message: "Unable to reach the PayPilot AI server. Check your connection.",
    });
  }

  const { status, data } = error.response;
  const errObj = data?.error;
  let message =
    errObj?.message ||
    (typeof data?.detail === "string" ? data.detail : null) ||
    `Request failed with status ${status}.`;

  if (Array.isArray(errObj?.details) && errObj.details.length > 0) {
    const firstMsg = errObj.details
      .map((d) => (d.field ? `${d.field.replace(/^body\./, "")}: ${d.message}` : d.message))
      .join(" | ");
    if (firstMsg) message = firstMsg;
  } else if (Array.isArray(data?.detail) && data.detail.length > 0) {
    message = data.detail.map((d) => d.msg || String(d)).join(" | ");
  }

  return new ApiError({
    status,
    code: errObj?.code || `HTTP_${status}`,
    message,
    details: errObj?.details || null,
  });
}

export const tokenVault = {
  setTokens({ accessToken, refreshToken }, rememberMe = false) {
    memoryAccessToken = accessToken || null;
    if (refreshToken !== undefined) {
      memoryRefreshToken = refreshToken || null;
    }

    try {
      window.sessionStorage.removeItem(ACCESS_STORAGE_KEY);
      window.localStorage.removeItem(ACCESS_STORAGE_KEY);
      if (accessToken) {
        if (rememberMe) {
          window.localStorage.setItem(ACCESS_STORAGE_KEY, accessToken);
          window.localStorage.setItem(REMEMBER_ME_KEY, "1");
        } else {
          window.sessionStorage.setItem(ACCESS_STORAGE_KEY, accessToken);
          window.localStorage.removeItem(REMEMBER_ME_KEY);
        }
      }
    } catch {
      // Ignore storage failures
    }
  },

  getAccessToken() {
    if (memoryAccessToken) return memoryAccessToken;
    try {
      const fromSession = window.sessionStorage.getItem(ACCESS_STORAGE_KEY);
      if (fromSession) {
        memoryAccessToken = fromSession;
        return fromSession;
      }
      const fromLocal = window.localStorage.getItem(ACCESS_STORAGE_KEY);
      if (fromLocal) {
        memoryAccessToken = fromLocal;
        return fromLocal;
      }
    } catch {
      // ignore
    }
    return null;
  },

  getRefreshToken() {
    return memoryRefreshToken;
  },

  isRemembered() {
    try {
      return window.localStorage.getItem(REMEMBER_ME_KEY) === "1";
    } catch {
      return false;
    }
  },

  clear() {
    memoryAccessToken = null;
    memoryRefreshToken = null;
    try {
      window.sessionStorage.removeItem(ACCESS_STORAGE_KEY);
      window.localStorage.removeItem(ACCESS_STORAGE_KEY);
      window.localStorage.removeItem(REMEMBER_ME_KEY);
    } catch {
      // ignore
    }
  },

  onSessionExpired(handler) {
    sessionExpiredHandler = handler;
  },
};

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 35000,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = tokenVault.getAccessToken();
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const status = error.response?.status;

    const isAuthEndpoint =
      originalRequest?.url?.includes("/auth/login") ||
      originalRequest?.url?.includes("/auth/register") ||
      originalRequest?.url?.includes("/auth/refresh");

    if (
      status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthEndpoint
    ) {
      const refreshToken = tokenVault.getRefreshToken();
      if (refreshToken) {
        originalRequest._retry = true;
        try {
          if (!refreshInFlight) {
            refreshInFlight = axios
              .post(
                `${API_BASE_URL}/api/v1/auth/refresh`,
                { refresh_token: refreshToken },
                {
                  timeout: 15000,
                  headers: { "Content-Type": "application/json" },
                }
              )
              .then((res) => {
                const { access_token, refresh_token } = res.data;
                tokenVault.setTokens(
                  {
                    accessToken: access_token,
                    refreshToken: refresh_token,
                  },
                  tokenVault.isRemembered()
                );
                return access_token;
              })
              .finally(() => {
                refreshInFlight = null;
              });
          }

          const nextAccessToken = await refreshInFlight;
          originalRequest.headers.Authorization = `Bearer ${nextAccessToken}`;
          return apiClient(originalRequest);
        } catch (refreshError) {
          tokenVault.clear();
          if (sessionExpiredHandler) {
            sessionExpiredHandler();
          }
          return Promise.reject(normalizeApiError(refreshError));
        }
      } else {
        tokenVault.clear();
        if (sessionExpiredHandler) {
          sessionExpiredHandler();
        }
      }
    }

    return Promise.reject(normalizeApiError(error));
  }
);

