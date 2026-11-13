import type { Metadata } from "next";
import { Suspense } from "react";
import { pageSheetWidth } from "@/components/ui/page-width";
import { CaseClosurePage } from "@/features/counseling/cases/case-closure-page";
import { EncounterDetailSkeleton } from "@/features/counseling/counseling-shared";

export const metadata: Metadata = { title: "Reopen counseling case" };

export default async function Page({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  return <div className={pageSheetWidth}><Suspense fallback={<EncounterDetailSkeleton />}><CaseClosurePage caseId={caseId} reopening /></Suspense></div>;
}
