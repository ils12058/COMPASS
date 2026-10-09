import type { Metadata } from "next";

import { GuidanceConversation } from "@/features/guidance-messages/guidance-conversation";

// The title never names the other participant: tab titles reach history and window lists.
export const metadata: Metadata = { title: "Conversation" };

export default async function Page({ params }: { params: Promise<{ threadId: string }> }) {
  const { threadId } = await params;
  return <GuidanceConversation threadId={threadId} />;
}
