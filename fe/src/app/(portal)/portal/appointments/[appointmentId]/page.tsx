import { Suspense } from "react";

import { AppointmentDetailSkeleton } from "@/features/appointments/appointments-shared";
import { AppointmentDetailPage } from "@/features/appointments/appointment-detail-page";

export default async function Page({
  params,
}: {
  params: Promise<{ appointmentId: string }>;
}) {
  const { appointmentId } = await params;
  return (
    <Suspense fallback={<AppointmentDetailSkeleton />}>
      <AppointmentDetailPage appointmentId={appointmentId} />
    </Suspense>
  );
}
