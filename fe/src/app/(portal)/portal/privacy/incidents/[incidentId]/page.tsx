import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { IncidentDetailPage } from "@/features/privacy-governance/incidents/incident-detail-page";

export const metadata: Metadata = { title: "Privacy Incident" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <IncidentDetailPage />
    </Suspense>
  );
}
