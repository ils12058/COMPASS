import { Suspense } from "react";

import { ServicesListSkeleton } from "@/features/services/services-shared";
import { ServicesListPage } from "@/features/services/services-list-page";

export default function Page() {
  return (
    <Suspense fallback={<ServicesListSkeleton />}>
      <ServicesListPage />
    </Suspense>
  );
}
