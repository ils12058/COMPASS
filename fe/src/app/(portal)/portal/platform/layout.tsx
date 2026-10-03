import type { Metadata } from "next";
import type { ReactNode } from "react";

import { PlatformGate } from "@/features/platform/platform-gate";
import { PlatformNavigation } from "@/features/platform/platform-navigation";

export const metadata: Metadata = {
  title: { default: "Platform Operations", template: "%s | COMPASS" },
};

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
