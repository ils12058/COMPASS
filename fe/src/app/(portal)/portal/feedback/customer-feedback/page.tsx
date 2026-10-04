import type { Metadata } from "next";

export const metadata: Metadata = { title: "Customer Feedback" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { FeedbackFormSkeleton } from "@/features/feedback/feedback-shared";
import { CustomerFeedbackForm } from "@/features/feedback/customer-feedback-form";

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<FeedbackFormSkeleton label="Loading Feedback service…" />}><CustomerFeedbackForm /></Suspense>
    </div>
  );
}
