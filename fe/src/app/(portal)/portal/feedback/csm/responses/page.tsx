import type { Metadata } from "next";

export const metadata: Metadata = { title: "Client Satisfaction Measurement responses" };

import { Suspense } from "react";

import { FeedbackListSkeleton } from "@/features/feedback/feedback-shared";
import { CsmResponseList } from "@/features/feedback/feedback-response-lists";

export default function Page() {
  return <Suspense fallback={<FeedbackListSkeleton label="Loading Client Satisfaction Measurement responses…" />}><CsmResponseList /></Suspense>;
}
