import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { AppointmentsMyPage } from "@/features/appointments/appointments-my-page";

export const metadata: Metadata = { title: "My appointments" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <AppointmentsMyPage />
    </Suspense>
  );
}
