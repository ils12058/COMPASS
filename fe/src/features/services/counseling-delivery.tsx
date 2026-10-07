"use client";

import Link from "next/link";

import { hasPlatformView } from "@/features/platform/platform-gate";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { DeliveryMode } from "@/lib/api/generated/model";

// Canonical Counseling only. Each delivery mode permits NEW Counseling work in that modality.
// ONLINE stays a delivery mode; E-Counseling is the workflow its scheduled Appointments use, and
// video-provider readiness is never inferred from Service configuration. Ordinary Services keep
// generic delivery wording (ADR-089).

export type CounselingDeliveryState = {
  inPerson: boolean;
  online: boolean;
  bookingEnabled: boolean;
};

export const counselingDeliveryOptions = [
  {
    mode: DeliveryMode.IN_PERSON,
    label: "In person",
    description: "In-person sessions.",
  },
  {
    mode: DeliveryMode.ONLINE,
    label: "Online counseling",
    description:
      "Scheduled sessions use E-Counseling.",
  },
] as const;

// What the current choice means for new work, shown whether or not Online is checked.
export function counselingOnlineStatus({
  inPerson,
  online,
  bookingEnabled,
}: CounselingDeliveryState): string {
  if (!online) {
    return "Online counseling off." + (inPerson ? " In-person Counseling remains available." : "");
  }
  if (!bookingEnabled) {
    return "Online counseling on. Appointment booking is off.";
  }
  return "Online counseling on. Appointment booking is available.";
}

export function newECounselingAppointmentsLabel({
  online,
  bookingEnabled,
}: CounselingDeliveryState): string {
  return online && bookingEnabled
    ? "Available for scheduling"
    : "Unavailable";
}

// Offered only to viewers who already hold Platform Operations access; it grants nothing new.
export function PlatformHealthLink({ className }: { className?: string }) {
  const { user } = usePortalSession();
  if (!hasPlatformView(user)) return null;
  return (
    <Link
      href="/portal/platform/health"
      className={
        className ??
        "inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      }
    >
      View Platform Health
    </Link>
  );
}
