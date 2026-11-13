import type { Metadata } from "next";
import { Suspense } from "react";
import { pageSheetWidth } from "@/components/ui/page-width";
import { CoverageReviewPage } from "@/features/counseling/continuity/coverage-review-page";
import { EncounterDetailSkeleton } from "@/features/counseling/counseling-shared";

export const metadata: Metadata = { title: "Coverage review" };
export default async function Page({ params }: { params: Promise<{ coverageId: string }> }) {
  const { coverageId } = await params;
  return <div className={pageSheetWidth}><Suspense fallback={<EncounterDetailSkeleton />}><CoverageReviewPage coverageId={coverageId} /></Suspense></div>;
}
