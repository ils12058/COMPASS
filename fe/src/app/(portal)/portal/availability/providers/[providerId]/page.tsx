import type { Metadata } from "next";
import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { AvailabilitySectionSkeleton } from "@/features/availability/availability-shared";
import { ProviderAvailabilityDetailPage } from "@/features/availability/availability-pages";

export const metadata: Metadata = { title: "Counselor Availability" };

export default async function Page({ params }: { params: Promise<{ providerId: string }> }) {
  const { providerId } = await params;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<AvailabilitySectionSkeleton label="Loading counselor availability…" />}>
        <ProviderAvailabilityDetailPage providerId={providerId} />
      </Suspense>
    </div>
  );
}
