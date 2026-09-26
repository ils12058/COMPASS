import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RetentionPoliciesPage } from "@/features/privacy-governance/retention-policies/retention-policies-page";

export const metadata: Metadata = { title: "Retention Policies" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <RetentionPoliciesPage />
    </Suspense>
  );
}
