import type { Metadata } from "next";
import { Suspense, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { PortalBoundary } from "@/features/portal/components/portal-boundary";

// An absolute title with no template would drop the root "%s | COMPASS"
// suffix for every portal page, so the portal restates it.
export const metadata: Metadata = {
  title: { absolute: "COMPASS", template: "%s | COMPASS" },
};

function PortalLoading() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md items-center px-5" aria-busy="true">
      <div className="w-full">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="mt-4 h-5 w-full" />
        <p className="sr-only">Checking your session…</p>
      </div>
    </main>
  );
}

export default function PortalLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<PortalLoading />}>
      <PortalBoundary>{children}</PortalBoundary>
    </Suspense>
  );
}
