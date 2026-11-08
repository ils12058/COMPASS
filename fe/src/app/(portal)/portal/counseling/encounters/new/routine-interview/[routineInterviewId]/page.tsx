import type { Metadata } from "next";

export const metadata: Metadata = { title: "Record Counseling Encounter" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { CounselingWorkspaceSkeleton } from "@/features/counseling/counseling-shared";
import { RecordEncounterPage } from "@/features/counseling/record-encounter-page";
import { CounselingContextAnchorType } from "@/lib/api/generated/model";

export default async function Page({ params }: { params: Promise<{ routineInterviewId: string }> }) {
  const { routineInterviewId } = await params;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<CounselingWorkspaceSkeleton />}>
        <RecordEncounterPage anchorType={CounselingContextAnchorType.ROUTINE_INTERVIEW} anchorId={routineInterviewId} from="workspace" />
      </Suspense>
    </div>
  );
}
