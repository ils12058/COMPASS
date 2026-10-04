import type { Metadata } from "next";
import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { FeedbackListSkeleton } from "@/features/feedback/feedback-shared";
import { FeedbackEntryPage } from "@/features/feedback/feedback-entry-page";

export const metadata: Metadata = { title: "Feedback" };

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<FeedbackListSkeleton label="Loading Feedback…" />}>
        <FeedbackEntryPage />
      </Suspense>
    </div>
  );
}
