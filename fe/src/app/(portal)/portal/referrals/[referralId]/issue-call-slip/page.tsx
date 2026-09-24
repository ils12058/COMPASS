import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { CallSlipFromReferralPage } from "@/features/call-slips/call-slip-from-referral-page";

export default async function Page({ params }: { params: Promise<{ referralId: string }> }) {
  const { referralId } = await params;
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <CallSlipFromReferralPage referralId={referralId} />
    </Suspense>
  );
}
