import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ProcessingActivityDetailPage } from "@/features/privacy-governance/processing-activities/processing-activity-detail-page";

export const metadata: Metadata = { title: "Processing Activity" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <ProcessingActivityDetailPage />
    </Suspense>
  );
}
