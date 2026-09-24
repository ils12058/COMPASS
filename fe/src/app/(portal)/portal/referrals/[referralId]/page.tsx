import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ReferralDetailPage } from "@/features/referrals/referral-detail-page";

export default async function Page({ params }: { params: Promise<{ referralId: string }> }) {
  const { referralId } = await params;
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <ReferralDetailPage referralId={referralId} />
    </Suspense>
  );
}
