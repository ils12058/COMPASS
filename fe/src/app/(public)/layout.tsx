import type { ReactNode } from "react";

import { PublicFooter } from "@/features/public/shell/public-footer";
import { PublicHeader } from "@/features/public/shell/public-header";
import { MaintenanceNotice, PublicMaintenanceGate } from "@/features/platform/maintenance-presentation";
import { scriptFontVariable } from "@/styles/script-font";

export default function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className={`${scriptFontVariable} flex min-h-dvh flex-col`}>
      {/* While maintenance is active the gate replaces the page; scheduled maintenance is a notice. */}
      <PublicMaintenanceGate>
        <PublicHeader />
        <div className="mx-auto w-full max-w-6xl px-5 pt-5 empty:hidden sm:px-8">
          <MaintenanceNotice />
        </div>
        <div className="flex-1">{children}</div>
        <PublicFooter />
      </PublicMaintenanceGate>
    </div>
  );
}
