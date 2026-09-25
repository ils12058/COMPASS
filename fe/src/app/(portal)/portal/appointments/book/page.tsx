import type { Metadata } from "next";

import { AppointmentBookingPage } from "@/features/appointments/appointment-booking-page";

export const metadata: Metadata = { title: "Book appointment" };

export default function Page() {
  return <AppointmentBookingPage />;
}
