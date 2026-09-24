import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { EncounterDetailPage } from "@/features/counseling/encounter-detail-page";

export default async function Page({ params }: { params: Promise<{ encounterId: string }> }) {
  const { encounterId } = await params;
  return <Suspense fallback={<Skeleton className="h-96 w-full" />}><EncounterDetailPage encounterId={encounterId} /></Suspense>;
}
