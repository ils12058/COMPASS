import type { Metadata } from "next";

export const metadata: Metadata = { title: "Shared Counseling Summary" };

import { Suspense } from "react";

import { SharedSummaryDetailSkeleton } from "@/features/counseling/counseling-shared";
import { StudentSharedSummaryDetail } from "@/features/counseling/student-shared-summaries";

export default async function Page({ params }: { params: Promise<{ summaryId: string }> }) {
  const { summaryId } = await params;
  return <Suspense fallback={<SharedSummaryDetailSkeleton />}><StudentSharedSummaryDetail summaryId={summaryId} /></Suspense>;
}
