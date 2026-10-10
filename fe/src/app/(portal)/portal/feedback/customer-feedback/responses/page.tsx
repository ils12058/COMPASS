import type { Metadata } from "next";

export const metadata: Metadata = { title: "Feedback Responses" };

import { Suspense } from "react";

import { FeedbackListSkeleton } from "@/features/feedback/feedback-shared";
import { CustomerFeedbackResponseList } from "@/features/feedback/feedback-response-lists";

export default function Page() {
  return <Suspense fallback={<FeedbackListSkeleton label="Loading Customer Feedback responses…" />}><CustomerFeedbackResponseList /></Suspense>;
}
