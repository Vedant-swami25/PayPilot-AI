import React, { useEffect } from "react";
import { AppRoutes } from "@/app/routes";
import { ToastContainer } from "@/components/ui/Toast";
import { useAppStore } from "@/store/useAppStore";

export default function App() {
  const theme = useAppStore((s) => s.theme);

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    root.classList.toggle("dark", theme === "dark");
  }, [theme]);

  useEffect(() => {
    const updateVisibility = () => {
      document.documentElement.setAttribute(
        "data-tab-inactive",
        document.hidden ? "true" : "false"
      );
    };
    updateVisibility();
    document.addEventListener("visibilitychange", updateVisibility);
    return () => {
      document.removeEventListener("visibilitychange", updateVisibility);
    };
  }, []);

  return (
    <>
      <AppRoutes />
      <ToastContainer />
    </>
  );
}

