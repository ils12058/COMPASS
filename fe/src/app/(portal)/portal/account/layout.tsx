import type { ReactNode } from "react";

import { AccountNavigation } from "@/features/account/components/account-navigation";

export default function AccountLayout({ children }: { children: ReactNode }) {
  return (
    <div className="max-w-4xl">
      <AccountNavigation />
      {children}
    </div>
  );
}
