import type { Metadata } from "next";
import type { ReactNode } from "react";

import {
  AvailabilityGate,
  AvailabilityNavigation,
} from "@/features/availability/availability-shared";

export const metadata: Metadata = { title: "Availability" };

export default function AvailabilityLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <AvailabilityGate>
      <AvailabilityNavigation />
      {children}
    </AvailabilityGate>
  );
}
