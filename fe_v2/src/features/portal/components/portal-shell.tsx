"use client";

import type { ReactNode } from "react";

import type { CurrentSessionResponse } from "@/lib/api/generated/model";
import { PortalDock } from "@/features/portal/components/portal-dock";

export function PortalShell({
  children,
  session,
}: {
  children: ReactNode;
  session: CurrentSessionResponse;
}) {
  return (
    <div className="min-h-screen bg-[var(--compass-surface-muted)] text-foreground">
      <a
        href="#portal-main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70] focus:rounded-lg focus:bg-card focus:px-4 focus:py-3 focus:font-semibold focus:shadow-md"
      >
        Skip to workspace
      </a>
      <PortalDock session={session} />
      <main
        id="portal-main"
        className="portal-shell__main min-h-screen px-4 py-6 sm:px-6 sm:py-8 lg:px-8"
      >
        <div className="mx-auto w-full max-w-7xl">{children}</div>
      </main>
    </div>
  );
}
