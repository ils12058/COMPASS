import type { ReactNode } from "react";

import { AccessibilityControl } from "@/features/accessibility/accessibility-control";
import { PublicFooter } from "@/features/public/shell/public-footer";
import { PublicHeader } from "@/features/public/shell/public-header";
import { MaintenanceNotice, PublicMaintenanceGate } from "@/features/platform/maintenance-presentation";
import { publicFontVariables } from "@/styles/public-fonts";

export default function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className={`${publicFontVariables} flex min-h-dvh flex-col`}>
      {/* While maintenance is active the gate replaces the page; scheduled maintenance is a notice. */}
      <PublicMaintenanceGate>
        <PublicHeader />
        <div className="mx-auto w-full max-w-6xl px-5 pt-5 empty:hidden sm:px-8">
          <MaintenanceNotice />
        </div>
        <div className="flex-1">{children}</div>
        <PublicFooter />
      </PublicMaintenanceGate>
      <AccessibilityControl placement="floating" />
    </div>
  );
}
