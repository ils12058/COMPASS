import type { Metadata } from "next";
import { Suspense } from "react";

import { AppointmentListSkeleton } from "@/features/appointments/appointments-shared";
import { AppointmentsMyPage } from "@/features/appointments/appointments-my-page";

export const metadata: Metadata = { title: "My appointments" };

export default function Page() {
  return (
    <Suspense fallback={<AppointmentListSkeleton />}>
      <AppointmentsMyPage />
    </Suspense>
  );
}
