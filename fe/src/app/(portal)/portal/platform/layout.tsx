import type { ReactNode } from "react";

import { PlatformGate } from "@/features/platform/platform-gate";
import { PlatformNavigation } from "@/features/platform/platform-navigation";

export default function PlatformLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <PlatformGate>
      <PlatformNavigation />
      {children}
    </PlatformGate>
  );
}
