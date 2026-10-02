import { Suspense } from "react";

import { ReferralDetailSkeleton } from "@/features/referrals/referrals-shared";
import { ReferralDetailPage } from "@/features/referrals/referral-detail-page";

export default async function Page({ params }: { params: Promise<{ referralId: string }> }) {
  const { referralId } = await params;
  return (
    <Suspense fallback={<ReferralDetailSkeleton />}>
      <ReferralDetailPage referralId={referralId} />
    </Suspense>
  );
}
