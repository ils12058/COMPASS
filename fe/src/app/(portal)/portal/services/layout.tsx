import type { ReactNode } from "react";

import { ServicesGate } from "@/features/services/services-shared";

export default function ServicesLayout({ children }: { children: ReactNode }) {
  return <ServicesGate>{children}</ServicesGate>;
}
