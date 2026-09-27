import type { Metadata } from "next";
import type { ReactNode } from "react";

import { ResourcesGate } from "@/features/resources/resources-gate";

export const metadata: Metadata = {
  title: { default: "Resources", template: "%s | COMPASS" },
};

export default function ResourcesLayout({ children }: { children: ReactNode }) {
  return <ResourcesGate>{children}</ResourcesGate>;
}
