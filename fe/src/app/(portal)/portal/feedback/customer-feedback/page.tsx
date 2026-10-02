import { Suspense } from "react";

import { FeedbackFormSkeleton } from "@/features/feedback/feedback-shared";
import { CustomerFeedbackForm } from "@/features/feedback/customer-feedback-form";

export default function Page() {
  return <Suspense fallback={<FeedbackFormSkeleton label="Loading Feedback service…" />}><CustomerFeedbackForm /></Suspense>;
}
