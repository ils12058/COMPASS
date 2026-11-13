import type { Metadata } from "next";
import { Suspense } from "react";
import { pageSheetWidth } from "@/components/ui/page-width";
import { CoveragePreparePage } from "@/features/counseling/continuity/coverage-prepare-page";
import { EncounterDetailSkeleton } from "@/features/counseling/counseling-shared";

export const metadata: Metadata = { title: "Arrange coverage" };
export default async function Page({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  return <div className={pageSheetWidth}><Suspense fallback={<EncounterDetailSkeleton />}><CoveragePreparePage caseId={caseId} /></Suspense></div>;
}
