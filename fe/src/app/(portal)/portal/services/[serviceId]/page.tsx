import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ServiceDetailPage } from "@/features/services/service-detail-page";

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <ServiceDetailPage />
    </Suspense>
  );
}
