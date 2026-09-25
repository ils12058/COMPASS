import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { CollegesPage } from "@/features/organization/colleges/colleges-page";
import { OrganizationStructureGate } from "@/features/organization/components/organization-gate";

export default function Page() {
  return (
    <OrganizationStructureGate>
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <CollegesPage />
      </Suspense>
    </OrganizationStructureGate>
  );
}
