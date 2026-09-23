import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ProviderAvailabilityPage } from "@/features/availability/availability-pages";

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <ProviderAvailabilityPage />
    </Suspense>
  );
}
