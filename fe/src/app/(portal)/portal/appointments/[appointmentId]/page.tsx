import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { AppointmentDetailPage } from "@/features/appointments/appointment-detail-page";

export default async function Page({
  params,
}: {
  params: Promise<{ appointmentId: string }>;
}) {
  const { appointmentId } = await params;
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <AppointmentDetailPage appointmentId={appointmentId} />
    </Suspense>
  );
}
