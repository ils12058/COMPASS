import type { Metadata } from "next";

export const metadata: Metadata = { title: "Record Counseling Encounter" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { CounselingWorkspaceSkeleton } from "@/features/counseling/counseling-shared";
import { encounterReturnTarget } from "@/features/counseling/encounter-origin";
import { RecordEncounterPage } from "@/features/counseling/record-encounter-page";
import { CounselingContextAnchorType } from "@/lib/api/generated/model";

export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ appointmentId: string }>;
  searchParams: Promise<{ from?: string | string[] }>;
}) {
  const { appointmentId } = await params;
  const { from } = await searchParams;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<CounselingWorkspaceSkeleton />}>
        <RecordEncounterPage anchorType={CounselingContextAnchorType.APPOINTMENT} anchorId={appointmentId} from={encounterReturnTarget(from)} />
      </Suspense>
    </div>
  );
}
