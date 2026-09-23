import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RoutineInterviewsEntryPage } from "@/features/routine-interviews/routine-interviews-entry-page";

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <RoutineInterviewsEntryPage />
    </Suspense>
  );
}
