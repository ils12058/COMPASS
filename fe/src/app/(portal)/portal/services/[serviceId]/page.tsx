import type { Metadata } from "next";

export const metadata: Metadata = { title: "Service Details" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { ServicesDetailSkeleton } from "@/features/services/services-shared";
import { ServiceDetailPage } from "@/features/services/service-detail-page";

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<ServicesDetailSkeleton />}>
        <ServiceDetailPage />
      </Suspense>
    </div>
  );
}
