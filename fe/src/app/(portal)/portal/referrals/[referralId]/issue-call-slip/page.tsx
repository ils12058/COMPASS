import type { Metadata } from "next";

export const metadata: Metadata = { title: "Issue Call Slip" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { LinkedCallSlipCheckLoading } from "@/features/call-slips/call-slips-shared";
import { CallSlipFromReferralPage } from "@/features/call-slips/call-slip-from-referral-page";

export default async function Page({ params }: { params: Promise<{ referralId: string }> }) {
  const { referralId } = await params;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<LinkedCallSlipCheckLoading />}>
        <CallSlipFromReferralPage referralId={referralId} />
      </Suspense>
    </div>
  );
}
