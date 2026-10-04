import type { Metadata } from "next";

export const metadata: Metadata = { title: "Referral Details" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { ReferralDetailSkeleton } from "@/features/referrals/referrals-shared";
import { ReferralDetailPage } from "@/features/referrals/referral-detail-page";

export default async function Page({ params }: { params: Promise<{ referralId: string }> }) {
  const { referralId } = await params;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<ReferralDetailSkeleton />}>
        <ReferralDetailPage referralId={referralId} />
      </Suspense>
    </div>
  );
}
