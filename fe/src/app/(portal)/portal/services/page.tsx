import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ServicesListPage } from "@/features/services/services-list-page";

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <ServicesListPage />
    </Suspense>
  );
}
