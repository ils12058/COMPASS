import type { Metadata } from "next";

export const metadata: Metadata = { title: "Appointment Details" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { AppointmentDetailSkeleton } from "@/features/appointments/appointments-shared";
import { AppointmentDetailPage } from "@/features/appointments/appointment-detail-page";

export default async function Page({
  params,
}: {
  params: Promise<{ appointmentId: string }>;
}) {
  const { appointmentId } = await params;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<AppointmentDetailSkeleton />}>
        <AppointmentDetailPage appointmentId={appointmentId} />
      </Suspense>
    </div>
  );
}
