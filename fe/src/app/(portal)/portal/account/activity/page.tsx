import type { Metadata } from "next";
import { Suspense } from "react";

import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { ActivityPage } from "@/features/account/activity/activity-page";

export const metadata: Metadata = { title: "Activity" };

export default function Page() {
  return (
    <Suspense fallback={<RowsSkeleton label="Loading activity…" rows={4} />}>
      <ActivityPage />
    </Suspense>
  );
}
