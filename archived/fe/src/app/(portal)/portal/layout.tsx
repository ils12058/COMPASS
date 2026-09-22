import type { ReactNode } from "react";

import { PortalAuthGate } from "@/features/auth/components/portal-auth-gate";
import { PortalShell } from "@/features/auth/components/portal-shell";

export default function PortalLayout({ children }: { children: ReactNode }) {
  return (
    <PortalAuthGate>
      <PortalShell>{children}</PortalShell>
    </PortalAuthGate>
  );
}
