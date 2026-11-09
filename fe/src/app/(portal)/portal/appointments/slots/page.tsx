import type { Metadata } from "next";

import { FixedSlotsManagementPage } from "@/features/appointments/fixed-slots-management-page";

export const metadata: Metadata = { title: "Manage Appointment slots" };

export default function Page() {
  return <FixedSlotsManagementPage />;
}
