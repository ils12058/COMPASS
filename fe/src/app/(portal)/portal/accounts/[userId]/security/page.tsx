import type { Metadata } from "next";

export const metadata: Metadata = { title: "Account Security" };

import { AccountSecurity } from "@/features/accounts/detail/security/account-security";

export default function Page() {
  return <AccountSecurity />;
}
