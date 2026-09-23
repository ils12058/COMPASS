"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { Skeleton } from "@/components/ui/skeleton";
import { AppointmentsUnavailable } from "@/features/appointments/appointments-shared";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function AppointmentsEntryPage() {
  const { user } = usePortalSession();
  const router = useRouter();
  const access = getAppointmentAccess(user);
  const destination = access.canViewSelf
    ? "/portal/appointments/my"
    : access.canManage
      ? "/portal/appointments/manage"
      : null;

  useEffect(() => {
    if (destination) router.replace(destination);
  }, [destination, router]);

  if (!destination) {
    return <AppointmentsUnavailable />;
  }
  return (
    <main aria-busy="true" className="max-w-3xl">
      <Skeleton className="h-8 w-2/5" />
      <Skeleton className="mt-5 h-20 w-full" />
      <p className="sr-only">Opening your Appointment workspace…</p>
    </main>
  );
}
