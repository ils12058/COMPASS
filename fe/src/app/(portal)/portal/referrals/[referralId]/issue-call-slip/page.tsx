import { Suspense } from "react";

import { LinkedCallSlipCheckLoading } from "@/features/call-slips/call-slips-shared";
import { CallSlipFromReferralPage } from "@/features/call-slips/call-slip-from-referral-page";

export default async function Page({ params }: { params: Promise<{ referralId: string }> }) {
  const { referralId } = await params;
  return (
    <Suspense fallback={<LinkedCallSlipCheckLoading />}>
      <CallSlipFromReferralPage referralId={referralId} />
    </Suspense>
  );
}
