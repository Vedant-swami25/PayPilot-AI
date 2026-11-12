/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        bg: {
          primary: "var(--bg-primary)",
          secondary: "var(--bg-secondary)",
          card: "var(--bg-card)",
          elevated: "var(--bg-elevated)",
        },
        text: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
        },
        brand: {
          navy: "#101828",
          slate: "#344054",
          emerald: "#16A36A",
          success: "#12B76A",
          error: "#D92D20",
        },
        border: {
          subtle: "var(--border-subtle)",
          strong: "var(--border-strong)",
          accent: "var(--border-accent)",
        },
      },
      boxShadow: {
        xs: "0 1px 2px rgba(16, 24, 40, 0.05)",
        card: "var(--shadow-card)",
        elevated: "var(--shadow-elevated)",
      },
    },
  },
  plugins: [],
};
