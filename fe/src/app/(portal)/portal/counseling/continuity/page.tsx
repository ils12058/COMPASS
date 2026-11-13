import { Suspense } from "react";
import { OfficeContinuityPage } from "@/features/counseling/continuity/office-continuity-page";
import { EncounterDetailSkeleton } from "@/features/counseling/counseling-shared";

export default function Page() {
  return <Suspense fallback={<EncounterDetailSkeleton />}><OfficeContinuityPage /></Suspense>;
}
