import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { CampusesPage } from "@/features/organization/campuses/campuses-page";

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <CampusesPage />
    </Suspense>
  );
}
