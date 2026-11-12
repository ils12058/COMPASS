import type { Metadata } from "next";
import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { CaseOverviewPage } from "@/features/counseling/cases/case-overview-page";
import { EncounterDetailSkeleton } from "@/features/counseling/counseling-shared";

export const metadata: Metadata = { title: "Counseling case" };

export default async function Page({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<EncounterDetailSkeleton />}><CaseOverviewPage caseId={caseId} /></Suspense>
    </div>
  );
}
