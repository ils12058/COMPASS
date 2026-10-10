import type { Metadata } from "next";

import { AccountPrivacyPage } from "@/features/account/privacy/account-privacy-page";

export const metadata: Metadata = { title: "Privacy" };

export default function Page() {
  return <AccountPrivacyPage />;
}
