import type { Metadata } from "next";
import type { ReactNode } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
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
  // The schedule editors need a bounded sheet, and the Counselors tab shares it so the tabs hold
  // one width.
  return (
    <div className={pageSheetWidth}>
      <AvailabilityGate>
        <AvailabilityNavigation />
        {children}
      </AvailabilityGate>
    </div>
  );
}
