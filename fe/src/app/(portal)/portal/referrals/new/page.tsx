import type { Metadata } from "next";

export const metadata: Metadata = { title: "Create Referral" };

import { ReferralCreatePage } from "@/features/referrals/referral-create-page";

export default function Page() {
  return <ReferralCreatePage />;
}
