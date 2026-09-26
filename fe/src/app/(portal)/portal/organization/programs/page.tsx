import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { OrganizationStructureGate } from "@/features/organization/components/organization-gate";
import { ProgramsPage } from "@/features/organization/programs/programs-page";

export default function Page() {
  return (
    <OrganizationStructureGate>
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <ProgramsPage />
      </Suspense>
    </OrganizationStructureGate>
  );
}
