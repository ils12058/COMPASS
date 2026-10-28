import type { Metadata } from "next";

import { FixedSlotsManagementPage } from "@/features/appointments/fixed-slots-management-page";

export const metadata: Metadata = { title: "Manage Appointment Slots" };

export default function Page() {
  return <FixedSlotsManagementPage />;
}
