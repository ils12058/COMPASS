import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { IncidentsPage } from "@/features/privacy-governance/incidents/incidents-page";

export const metadata: Metadata = { title: "Privacy Incidents" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <IncidentsPage />
    </Suspense>
  );
}
