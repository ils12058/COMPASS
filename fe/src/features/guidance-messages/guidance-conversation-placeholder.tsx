"use client";

import { MessagesSquare } from "lucide-react";

import { useGuidanceWorkspace } from "@/features/guidance-messages/guidance-messages-workspace";

// The conversation pane before a conversation is chosen. Narrow screens show only the directory.
export function GuidanceConversationPlaceholder() {
  const { access } = useGuidanceWorkspace();
  const canStart = access.canManageSelf || access.canManageStaff;
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
      <MessagesSquare size={24} aria-hidden="true" className="text-muted" />
      <p className="text-sm text-muted">
        {canStart ? "Choose a conversation, or start a new message." : "Choose a conversation to read it."}
      </p>
    </div>
  );
}
