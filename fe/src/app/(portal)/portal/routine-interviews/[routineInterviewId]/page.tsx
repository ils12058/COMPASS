import { Suspense } from "react";

import { RoutineInterviewDetailSkeleton } from "@/features/routine-interviews/routine-interviews-shared";
import { RoutineInterviewDetailPage } from "@/features/routine-interviews/routine-interview-detail-page";

export default async function Page({
  params,
}: {
  params: Promise<{ routineInterviewId: string }>;
}) {
  const { routineInterviewId } = await params;

  return (
    <Suspense fallback={<RoutineInterviewDetailSkeleton />}>
      <RoutineInterviewDetailPage routineInterviewId={routineInterviewId} />
    </Suspense>
  );
}
