import type { Metadata } from "next";

export const metadata: Metadata = { title: "Student Session Summary" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { StudentSessionSummaryDetailSkeleton } from "@/features/counseling/counseling-shared";
import { StudentSessionSummaryDetail } from "@/features/counseling/student-session-summaries";

export default async function Page({ params }: { params: Promise<{ summaryId: string }> }) {
  const { summaryId } = await params;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<StudentSessionSummaryDetailSkeleton />}><StudentSessionSummaryDetail summaryId={summaryId} /></Suspense>
    </div>
  );
}
