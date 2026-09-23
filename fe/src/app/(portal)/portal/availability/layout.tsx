import type { ReactNode } from "react";

import {
  AvailabilityGate,
  AvailabilityNavigation,
} from "@/features/availability/availability-shared";

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
