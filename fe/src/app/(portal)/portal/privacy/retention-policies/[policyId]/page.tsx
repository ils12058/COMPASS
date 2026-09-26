import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RetentionPolicyDetailPage } from "@/features/privacy-governance/retention-policies/retention-policy-detail-page";

export const metadata: Metadata = { title: "Retention Policy" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <RetentionPolicyDetailPage />
    </Suspense>
  );
}
