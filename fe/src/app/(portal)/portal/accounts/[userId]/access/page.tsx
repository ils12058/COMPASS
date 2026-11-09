import type { Metadata } from "next";

export const metadata: Metadata = { title: "Account access" };

import { AccountAccess } from "@/features/accounts/detail/access/account-access";

export default function Page() {
  return <AccountAccess />;
}
