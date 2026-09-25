import type { Metadata } from "next";

import { FeedbackEntryPage } from "@/features/feedback/feedback-entry-page";

export const metadata: Metadata = { title: "Feedback" };

export default function Page() {
  return <FeedbackEntryPage />;
}
