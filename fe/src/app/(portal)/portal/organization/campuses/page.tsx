import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { CampusesPage } from "@/features/organization/campuses/campuses-page";
import { OrganizationStructureGate } from "@/features/organization/components/organization-gate";

export default function Page() {
  return (
    <OrganizationStructureGate>
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <CampusesPage />
      </Suspense>
    </OrganizationStructureGate>
  );
}
