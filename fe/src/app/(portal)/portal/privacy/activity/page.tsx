import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { PrivacyActivityPage } from "@/features/privacy-governance/activity/privacy-activity-page";

export const metadata: Metadata = { title: "Privacy & Security Activity" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <PrivacyActivityPage />
    </Suspense>
  );
}
