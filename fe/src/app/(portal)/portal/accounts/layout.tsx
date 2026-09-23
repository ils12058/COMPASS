import type { ReactNode } from "react";

import { AccountsGate } from "@/features/accounts/components/accounts-gate";

export default function AccountsLayout({ children }: { children: ReactNode }) {
  return <AccountsGate>{children}</AccountsGate>;
}
