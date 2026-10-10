import type { Metadata } from "next";

export const metadata: Metadata = { title: "Customer Satisfaction Measurement" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { FeedbackFormSkeleton } from "@/features/feedback/feedback-shared";
import { CsmForm } from "@/features/feedback/csm-form";

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<FeedbackFormSkeleton label="Loading Feedback service…" />}><CsmForm /></Suspense>
    </div>
  );
}
