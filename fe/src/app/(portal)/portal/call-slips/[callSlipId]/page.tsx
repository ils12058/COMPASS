import type { Metadata } from "next";

export const metadata: Metadata = { title: "Call Slip Details" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { CallSlipDetailSkeleton } from "@/features/call-slips/call-slips-shared";
import { CallSlipDetailPage } from "@/features/call-slips/call-slip-detail-page";

export default async function Page({ params }: { params: Promise<{ callSlipId: string }> }) {
  const { callSlipId } = await params;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<CallSlipDetailSkeleton />}>
        <CallSlipDetailPage callSlipId={callSlipId} />
      </Suspense>
    </div>
  );
}
