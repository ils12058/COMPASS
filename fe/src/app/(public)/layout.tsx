import type { ReactNode } from "react";

import { PublicFooter } from "@/features/public/shell/public-footer";
import { PublicHeader } from "@/features/public/shell/public-header";

export default function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <PublicHeader />
      <div className="flex-1">{children}</div>
      <PublicFooter />
    </div>
  );
}
