import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { AppointmentBookingPage } from "@/features/appointments/appointment-booking-page";

export const metadata: Metadata = { title: "Book appointment" };

export default async function Page({ searchParams }: { searchParams: Promise<{ pathway?: string }> }) {
  const query = await searchParams;
  return (
    <div className={pageSheetWidth}>
      <AppointmentBookingPage scheduledSlots={query.pathway === "FIXED_DATE_SLOT"} />
    </div>
  );
}
