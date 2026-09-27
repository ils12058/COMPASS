import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ResourcesListPage } from "@/features/resources/resources-list-page";

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <ResourcesListPage />
    </Suspense>
  );
}
