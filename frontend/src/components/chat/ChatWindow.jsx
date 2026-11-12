import React, { useEffect, useRef } from "react";
import { TypingIndicator } from "./TypingIndicator";

export function ChatWindow({ children, isProcessing = false, processingText = "" }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [children, isProcessing]);

  return (
    <div className="flex-1 overflow-y-auto space-y-4 pr-1 py-2">
      {children}
      {isProcessing && <TypingIndicator label={processingText || undefined} />}
      <div ref={bottomRef} />
    </div>
  );
}

