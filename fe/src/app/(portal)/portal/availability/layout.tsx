import type { Metadata } from "next";
import type { ReactNode } from "react";

import {
  AvailabilityGate,
  AvailabilityNavigation,
} from "@/features/availability/availability-shared";

export const metadata: Metadata = {
  title: { default: "Availability", template: "%s | COMPASS" },
};

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
