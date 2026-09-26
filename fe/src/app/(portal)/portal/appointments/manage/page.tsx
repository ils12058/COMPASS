import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { AppointmentsManagedPage } from "@/features/appointments/appointments-managed-page";

export const metadata: Metadata = { title: "Manage appointments" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <AppointmentsManagedPage />
    </Suspense>
  );
}
