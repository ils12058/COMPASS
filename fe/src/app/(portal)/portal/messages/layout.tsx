import type { Metadata } from "next";
import type { ReactNode } from "react";

import { GuidanceMessagesWorkspace } from "@/features/guidance-messages/guidance-messages-workspace";

export const metadata: Metadata = { title: "Messages" };

// The workspace (directory and conversation pane) stays mounted while the reader moves between
// conversations; each route below fills the conversation pane.
export default function MessagesLayout({ children }: { children: ReactNode }) {
  return <GuidanceMessagesWorkspace>{children}</GuidanceMessagesWorkspace>;
}
