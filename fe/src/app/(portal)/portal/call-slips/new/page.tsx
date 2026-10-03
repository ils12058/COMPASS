import type { Metadata } from "next";

export const metadata: Metadata = { title: "Issue Call Slip" };

import { Suspense } from "react";

import { CallSlipDetailSkeleton } from "@/features/call-slips/call-slips-shared";
import { DirectCallSlipCreatePage } from "@/features/call-slips/call-slip-create-page";

export default function Page() {
  return (
    <Suspense fallback={<CallSlipDetailSkeleton label="Loading Call Slip issuance…" />}>
      <DirectCallSlipCreatePage />
    </Suspense>
  );
}
