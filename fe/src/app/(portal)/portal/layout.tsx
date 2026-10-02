import type { Metadata } from "next";
import { Suspense, type ReactNode } from "react";

import { PortalBoundary } from "@/features/portal/components/portal-boundary";
import { PortalSessionLoading } from "@/features/portal/components/portal-session-loading";

// An absolute title with no template would drop the root "%s | COMPASS"
// suffix for every portal page, so the portal restates it.
export const metadata: Metadata = {
  title: { absolute: "COMPASS", template: "%s | COMPASS" },
  robots: { index: false, follow: false },
};

export default function PortalLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<PortalSessionLoading />}>
      <PortalBoundary>{children}</PortalBoundary>
    </Suspense>
  );
}
