import type { Metadata } from "next";
import { Suspense } from "react";
import { pageSheetWidth } from "@/components/ui/page-width";
import { EncounterDetailSkeleton } from "@/features/counseling/counseling-shared";
import { ReassignmentReviewPage } from "@/features/counseling/reassignment/reassignment-review-page";

export const metadata: Metadata = { title: "Session reassignment" };
export default async function Page({ params }: { params: Promise<{ reassignmentId: string }> }) {
  const { reassignmentId } = await params;
  return <div className={pageSheetWidth}><Suspense fallback={<EncounterDetailSkeleton />}><ReassignmentReviewPage reassignmentId={reassignmentId} /></Suspense></div>;
}
