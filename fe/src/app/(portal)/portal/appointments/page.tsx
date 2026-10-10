import type { Metadata } from "next";

import { AppointmentsEntryPage } from "@/features/appointments/appointments-entry-page";

export const metadata: Metadata = { title: "Appointments" };

export default function Page() {
  return <AppointmentsEntryPage />;
}
