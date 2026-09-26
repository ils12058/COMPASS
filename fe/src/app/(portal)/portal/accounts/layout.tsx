import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AccountsGate } from "@/features/accounts/components/accounts-gate";

export const metadata: Metadata = { title: "Accounts" };

export default function AccountsLayout({ children }: { children: ReactNode }) {
  return <AccountsGate>{children}</AccountsGate>;
}
