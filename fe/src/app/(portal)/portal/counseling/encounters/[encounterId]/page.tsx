import { Suspense } from "react";

import { EncounterDetailSkeleton } from "@/features/counseling/counseling-shared";
import { EncounterDetailPage } from "@/features/counseling/encounter-detail-page";

export default async function Page({ params }: { params: Promise<{ encounterId: string }> }) {
  const { encounterId } = await params;
  return <Suspense fallback={<EncounterDetailSkeleton />}><EncounterDetailPage encounterId={encounterId} /></Suspense>;
}
