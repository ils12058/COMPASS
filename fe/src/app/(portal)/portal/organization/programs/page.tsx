import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ProgramsPage } from "@/features/organization/programs/programs-page";

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <ProgramsPage />
    </Suspense>
  );
}
