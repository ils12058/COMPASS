import type { Metadata } from "next";

import { GuidanceNewMessage } from "@/features/guidance-messages/guidance-new-message";

export const metadata: Metadata = { title: "New message" };

export default function Page() {
  return <GuidanceNewMessage />;
}
