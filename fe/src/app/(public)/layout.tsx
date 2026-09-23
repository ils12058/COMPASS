import type { ReactNode } from "react";

import { PublicFooter } from "@/features/public/shell/public-footer";
import { PublicHeader } from "@/features/public/shell/public-header";
import { PublicMaintenanceNotice } from "@/features/platform/platform-public-maintenance-notice";

export default function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <PublicHeader />
      <div className="mx-auto w-full max-w-6xl px-5 sm:px-8">
        <PublicMaintenanceNotice />
      </div>
      <div className="flex-1">{children}</div>
      <PublicFooter />
    </div>
  );
}
