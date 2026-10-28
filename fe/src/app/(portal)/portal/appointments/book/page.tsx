import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { AppointmentBookingPage } from "@/features/appointments/appointment-booking-page";

export const metadata: Metadata = { title: "Book appointment" };

export default async function Page({ searchParams }: { searchParams: Promise<{ pathway?: string | string[]; service_id?: string | string[]; search?: string | string[]; page?: string | string[] }> }) {
  const query = await searchParams;
  const single = (value: string | string[] | undefined) => typeof value === "string" ? value : undefined;
  return (
    <div className={pageSheetWidth}>
      <AppointmentBookingPage scheduledSlots={single(query.pathway) === "FIXED_DATE_SLOT"} serviceId={single(query.service_id)} initialSearch={single(query.search)} initialPage={single(query.page)} />
    </div>
  );
}
