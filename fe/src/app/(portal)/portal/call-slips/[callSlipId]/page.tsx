import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { CallSlipDetailPage } from "@/features/call-slips/call-slip-detail-page";

export default async function Page({ params }: { params: Promise<{ callSlipId: string }> }) {
  const { callSlipId } = await params;
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <CallSlipDetailPage callSlipId={callSlipId} />
    </Suspense>
  );
}
