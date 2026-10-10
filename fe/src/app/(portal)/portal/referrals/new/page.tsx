import type { Metadata } from "next";

export const metadata: Metadata = { title: "Create Referral" };

import { pageSheetWidth } from "@/components/ui/page-width";
import { ReferralCreatePage } from "@/features/referrals/referral-create-page";

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <ReferralCreatePage />
    </div>
  );
}
