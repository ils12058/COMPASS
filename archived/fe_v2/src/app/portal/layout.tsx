import type { Metadata } from "next";
import type { ReactNode } from "react";

import { PortalGate } from "@/features/portal/components/portal-gate";

export const metadata: Metadata = {
  title: {
    default: "Workspace",
    template: "%s | COMPASS",
  },
  robots: {
    index: false,
    follow: false,
  },
};

export default function PortalLayout({ children }: { children: ReactNode }) {
  return <PortalGate>{children}</PortalGate>;
}
