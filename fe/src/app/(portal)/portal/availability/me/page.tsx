import type { Metadata } from "next";

export const metadata: Metadata = { title: "My Availability" };

import { MyAvailabilityPage } from "@/features/availability/availability-pages";

export default function Page() {
  return <MyAvailabilityPage />;
}
