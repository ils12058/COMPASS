import type { Metadata } from "next";

export const metadata: Metadata = { title: "CSM Responses" };

import { Suspense } from "react";

import { FeedbackListSkeleton } from "@/features/feedback/feedback-shared";
import { CsmResponseList } from "@/features/feedback/feedback-response-lists";

export default function Page() {
  return <Suspense fallback={<FeedbackListSkeleton label="Loading CSM responses…" />}><CsmResponseList /></Suspense>;
}
