import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ExitInterviewDetailPage } from "@/features/exit-interviews/exit-interview-detail-page";

export default async function Page({
  params,
}: {
  params: Promise<{ exitInterviewId: string }>;
}) {
  const { exitInterviewId } = await params;
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <ExitInterviewDetailPage exitInterviewId={exitInterviewId} />
    </Suspense>
  );
}
