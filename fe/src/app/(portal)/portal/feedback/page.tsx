import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { FeedbackEntryPage } from "@/features/feedback/feedback-entry-page";

export const metadata: Metadata = { title: "Feedback" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <FeedbackEntryPage />
    </Suspense>
  );
}
