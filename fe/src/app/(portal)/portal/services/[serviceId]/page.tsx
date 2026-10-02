import { Suspense } from "react";

import { ServicesDetailSkeleton } from "@/features/services/services-shared";
import { ServiceDetailPage } from "@/features/services/service-detail-page";

export default function Page() {
  return (
    <Suspense fallback={<ServicesDetailSkeleton />}>
      <ServiceDetailPage />
    </Suspense>
  );
}
