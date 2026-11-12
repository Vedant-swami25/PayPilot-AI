import React from "react";
import { Search, User } from "lucide-react";

export function ChatMessage({
  role = "assistant",
  title = null,
  content,
  timestamp = null,
  children = null,
}) {
  const isUser = role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#ECFDF3] border border-[#ABEFC6] text-[#16A36A] mt-0.5 dark:bg-emerald-500/15 dark:border-emerald-500/30 dark:text-emerald-300">
          <Search className="h-4 w-4" />
        </div>
      )}

      <div
        className={`max-w-[88%] sm:max-w-[82%] rounded-xl px-4 py-3 text-sm ${
          isUser
            ? "bg-[#101828] text-white dark:bg-[#1E293B]"
            : "bg-bg-primary border border-border-subtle text-text-primary"
        }`}
      >
        {title && (
          <p className="text-xs font-semibold text-[#16A36A] mb-1">{title}</p>
        )}
        {content && (
          <p className="whitespace-pre-wrap leading-relaxed text-sm">{content}</p>
        )}
        {children && <div className="mt-3">{children}</div>}
        {timestamp && (
          <p
            className={`mt-1.5 text-[10px] text-right ${
              isUser ? "text-slate-300" : "text-text-muted"
            }`}
          >
            {timestamp}
          </p>
        )}
      </div>

      {isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-bg-secondary border border-border-subtle text-text-secondary mt-0.5">
          <User className="h-4 w-4" />
        </div>
      )}
    </div>
  );
}

