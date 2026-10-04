import type { Metadata } from "next";

export const metadata: Metadata = { title: "Issue Call Slip" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { CallSlipDetailSkeleton } from "@/features/call-slips/call-slips-shared";
import { DirectCallSlipCreatePage } from "@/features/call-slips/call-slip-create-page";

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<CallSlipDetailSkeleton label="Loading Call Slip issuance…" />}>
        <DirectCallSlipCreatePage />
      </Suspense>
    </div>
  );
}
