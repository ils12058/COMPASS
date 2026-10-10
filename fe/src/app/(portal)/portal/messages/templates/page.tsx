import type { Metadata } from "next";

import { GuidanceMessageTemplatesPage } from "@/features/guidance-messages/guidance-message-templates-page";

export const metadata: Metadata = { title: "Message templates" };

// Outside the conversations layout: managing shared templates is a page of its own, not a pane of
// the chat workspace.
export default function Page() {
  return <GuidanceMessageTemplatesPage />;
}
