import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { StudentSharedSummaryDetail } from "@/features/counseling/student-shared-summaries";

export default async function Page({ params }: { params: Promise<{ summaryId: string }> }) {
  const { summaryId } = await params;
  return <Suspense fallback={<Skeleton className="h-96 w-full" />}><StudentSharedSummaryDetail summaryId={summaryId} /></Suspense>;
}
