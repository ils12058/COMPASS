import type { Metadata } from "next";

export const metadata: Metadata = { title: "Provider Availability" };

import { Suspense } from "react";

import { AvailabilitySectionSkeleton } from "@/features/availability/availability-shared";
import { ProviderAvailabilityPage } from "@/features/availability/availability-pages";

export default function Page() {
  return (
    <Suspense fallback={<AvailabilitySectionSkeleton label="Loading Counselors…" />}>
      <ProviderAvailabilityPage />
    </Suspense>
  );
}
