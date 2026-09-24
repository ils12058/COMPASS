import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { CounselingWorkspace } from "@/features/counseling/counseling-workspace";
import { CounselingContextAnchorType } from "@/lib/api/generated/model";

export default async function Page({ params }: { params: Promise<{ routineInterviewId: string }> }) {
  const { routineInterviewId } = await params;
  return <Suspense fallback={<Skeleton className="h-96 w-full" />}><CounselingWorkspace anchorType={CounselingContextAnchorType.ROUTINE_INTERVIEW} anchorId={routineInterviewId} /></Suspense>;
}
