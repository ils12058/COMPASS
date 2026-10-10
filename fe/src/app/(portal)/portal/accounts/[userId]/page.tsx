import type { Metadata } from "next";

export const metadata: Metadata = { title: "Account Details" };

import { AccountOverview } from "@/features/accounts/detail/overview/account-overview";

export default function Page() {
  return <AccountOverview />;
}
