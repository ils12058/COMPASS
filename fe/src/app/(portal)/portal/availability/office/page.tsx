import type { Metadata } from "next";

export const metadata: Metadata = { title: "Office Availability" };

import { OfficeAvailabilityPage } from "@/features/availability/availability-pages";

export default function Page() {
  return <OfficeAvailabilityPage />;
}
