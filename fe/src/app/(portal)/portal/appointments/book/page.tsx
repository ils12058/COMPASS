import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { AppointmentBookingPage } from "@/features/appointments/appointment-booking-page";

export const metadata: Metadata = { title: "Book appointment" };

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <AppointmentBookingPage />
    </div>
  );
}
