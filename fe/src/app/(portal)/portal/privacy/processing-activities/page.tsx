import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ProcessingActivitiesPage } from "@/features/privacy-governance/processing-activities/processing-activities-page";

export const metadata: Metadata = { title: "Processing Activities" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <ProcessingActivitiesPage />
    </Suspense>
  );
}
