import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RoutineInterviewDetailPage } from "@/features/routine-interviews/routine-interview-detail-page";

export default async function Page({
  params,
}: {
  params: Promise<{ routineInterviewId: string }>;
}) {
  const { routineInterviewId } = await params;

  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <RoutineInterviewDetailPage routineInterviewId={routineInterviewId} />
    </Suspense>
  );
}
