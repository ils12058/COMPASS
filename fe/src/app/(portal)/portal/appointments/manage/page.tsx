import type { Metadata } from "next";
import { Suspense } from "react";

import { AppointmentListSkeleton } from "@/features/appointments/appointments-shared";
import { AppointmentsManagedPage } from "@/features/appointments/appointments-managed-page";

export const metadata: Metadata = { title: "Manage appointments" };

export default function Page() {
  return (
    <Suspense fallback={<AppointmentListSkeleton />}>
      <AppointmentsManagedPage />
    </Suspense>
  );
}
