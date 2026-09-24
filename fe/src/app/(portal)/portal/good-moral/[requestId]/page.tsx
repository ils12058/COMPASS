import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { GoodMoralDetailPage } from "@/features/good-moral/good-moral-detail-page";

export default async function Page({ params }: { params: Promise<{ requestId: string }> }) {
  const { requestId } = await params;
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <GoodMoralDetailPage requestId={requestId} />
    </Suspense>
  );
}
