import { create } from "zustand";

const THEME_KEY = "paypilot_theme";
const COMPARE_KEY = "paypilot_compare_ids";
const AI_PREFS_KEY = "paypilot_ai_prefs";
const RECENT_PROMPTS_KEY = "paypilot_recent_prompts";

function readStorage(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function writeStorage(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage quota errors
  }
}

const initialTheme = (() => {
  try {
    const saved = window.localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // ignore
  }
  return "light";
})();

export const useAppStore = create((set, get) => ({
  theme: initialTheme,
  sidebarCollapsed: false,
  mobileNavOpen: false,
  compareIds: readStorage(COMPARE_KEY, []),
  activeWorkflowId: null,
  recentCommands: readStorage(RECENT_PROMPTS_KEY, []),
  aiPreferences: readStorage(AI_PREFS_KEY, {
    autoExpandReasoning: true,
    preferredCurrency: "USD",
    conciseSummaries: false,
  }),
  toasts: [],

  setTheme: (theme) => {
    const next = theme === "light" ? "light" : "dark";
    try {
      window.localStorage.setItem(THEME_KEY, next);
    } catch {
      // ignore
    }
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-theme", next);
      document.documentElement.classList.toggle("dark", next === "dark");
    }
    set({ theme: next });
  },

  toggleTheme: () => {
    const next = get().theme === "dark" ? "light" : "dark";
    get().setTheme(next);
  },

  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  setMobileNavOpen: (open) => set({ mobileNavOpen: open }),
  setActiveWorkflowId: (workflowId) => set({ activeWorkflowId: workflowId }),

  addRecentCommand: (command) => {
    const cleaned = (command || "").trim();
    if (!cleaned) return;
    const prev = get().recentCommands.filter((c) => c !== cleaned);
    const next = [cleaned, ...prev].slice(0, 8);
    writeStorage(RECENT_PROMPTS_KEY, next);
    set({ recentCommands: next });
  },

  toggleCompareProduct: (productId) => {
    if (!productId) return;
    const current = get().compareIds;
    let next;
    if (current.includes(productId)) {
      next = current.filter((id) => id !== productId);
    } else {
      if (current.length >= 4) {
        get().pushToast({
          title: "Comparison limit reached",
          description: "Compare up to 4 products at a time.",
          variant: "warning",
        });
        return;
      }
      next = [...current, productId];
    }
    writeStorage(COMPARE_KEY, next);
    set({ compareIds: next });
  },

  clearCompareProducts: () => {
    writeStorage(COMPARE_KEY, []);
    set({ compareIds: [] });
  },

  updateAIPreferences: (patch) => {
    const next = { ...get().aiPreferences, ...patch };
    writeStorage(AI_PREFS_KEY, next);
    set({ aiPreferences: next });
  },

  pushToast: ({ title, description, variant = "info", duration = 4500 }) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    set((state) => ({
      toasts: [...state.toasts, { id, title, description, variant }],
    }));
    if (duration > 0) {
      window.setTimeout(() => {
        get().dismissToast(id);
      }, duration);
    }
    return id;
  },

  dismissToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}));

