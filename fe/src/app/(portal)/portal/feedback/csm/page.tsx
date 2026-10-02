import { Suspense } from "react";

import { FeedbackFormSkeleton } from "@/features/feedback/feedback-shared";
import { CsmForm } from "@/features/feedback/csm-form";

export default function Page() {
  return <Suspense fallback={<FeedbackFormSkeleton label="Loading Feedback service…" />}><CsmForm /></Suspense>;
}
