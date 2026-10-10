import type { Metadata } from "next";

export const metadata: Metadata = { title: "Routine Interview Details" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { RoutineInterviewDetailSkeleton } from "@/features/routine-interviews/routine-interviews-shared";
import { RoutineInterviewDetailPage } from "@/features/routine-interviews/routine-interview-detail-page";

export default async function Page({
  params,
}: {
  params: Promise<{ routineInterviewId: string }>;
}) {
  const { routineInterviewId } = await params;

  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<RoutineInterviewDetailSkeleton />}>
        <RoutineInterviewDetailPage routineInterviewId={routineInterviewId} />
      </Suspense>
    </div>
  );
}
