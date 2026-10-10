import type { Metadata } from "next";
import { Suspense } from "react";

import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { PlatformActivityPage } from "@/features/platform/activity/platform-activity-page";

export const metadata: Metadata = { title: "Platform Activity" };

export default function Page() {
  return (
    <Suspense fallback={<RowsSkeleton label="Loading activity…" rows={4} />}>
      <PlatformActivityPage />
    </Suspense>
  );
}
