import type { Metadata } from "next";

export const metadata: Metadata = { title: "Counseling Encounter" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { EncounterDetailSkeleton } from "@/features/counseling/counseling-shared";
import { EncounterDetailPage } from "@/features/counseling/encounter-detail-page";

export default async function Page({ params }: { params: Promise<{ encounterId: string }> }) {
  const { encounterId } = await params;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<EncounterDetailSkeleton />}><EncounterDetailPage encounterId={encounterId} /></Suspense>
    </div>
  );
}
