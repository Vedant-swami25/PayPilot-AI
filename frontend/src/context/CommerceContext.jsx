import React, { createContext, useMemo } from "react";
import { useAppStore } from "@/store/useAppStore";

export const CommerceContext = createContext(null);

export function CommerceProvider({ children }) {
  const compareIds = useAppStore((s) => s.compareIds);
  const toggleCompareProduct = useAppStore((s) => s.toggleCompareProduct);
  const clearCompareProducts = useAppStore((s) => s.clearCompareProducts);
  const activeWorkflowId = useAppStore((s) => s.activeWorkflowId);
  const setActiveWorkflowId = useAppStore((s) => s.setActiveWorkflowId);

  const value = useMemo(
    () => ({
      compareIds,
      toggleCompareProduct,
      clearCompareProducts,
      activeWorkflowId,
      setActiveWorkflowId,
    }),
    [
      compareIds,
      toggleCompareProduct,
      clearCompareProducts,
      activeWorkflowId,
      setActiveWorkflowId,
    ]
  );

  return (
    <CommerceContext.Provider value={value}>
      {children}
    </CommerceContext.Provider>
  );
}

