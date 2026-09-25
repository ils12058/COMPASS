import type { Metadata } from "next";
import type { ReactNode } from "react";

import { ServicesGate } from "@/features/services/services-shared";

export const metadata: Metadata = { title: "Services" };

export default function ServicesLayout({ children }: { children: ReactNode }) {
  return <ServicesGate>{children}</ServicesGate>;
}
