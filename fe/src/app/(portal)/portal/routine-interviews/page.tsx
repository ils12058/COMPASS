import type { Metadata } from "next";
import { Suspense } from "react";

import { RoutineInterviewListSkeleton } from "@/features/routine-interviews/routine-interviews-shared";
import { RoutineInterviewsEntryPage } from "@/features/routine-interviews/routine-interviews-entry-page";

export const metadata: Metadata = { title: "Routine Interviews" };

export default function Page() {
  return (
    <Suspense fallback={<RoutineInterviewListSkeleton label="Loading Routine Interviews…" />}>
      <RoutineInterviewsEntryPage />
    </Suspense>
  );
}
