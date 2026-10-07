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
    description: "Permits new in-person Counseling.",
  },
  {
    mode: DeliveryMode.ONLINE,
    label: "Online counseling",
    description:
      "Permits new online Counseling. Scheduled Online Counseling appointments use the E-Counseling workspace.",
  },
] as const;

export const counselingVideoProviderNote =
  "Video-session availability also depends on the E-Counseling provider configuration, which is managed separately.";

// What the current choice means for new work, shown whether or not Online is checked.
export function counselingOnlineStatus({
  inPerson,
  online,
  bookingEnabled,
}: CounselingDeliveryState): string {
  if (!online) {
    return (
      "Online counseling is not enabled. New Online Counseling appointments cannot be scheduled, " +
      "so no new appointments can enter E-Counseling." +
      (inPerson ? " In-person Counseling is not affected." : "")
    );
  }
  if (!bookingEnabled) {
    return (
      "Online counseling is enabled for new Counseling work, but Appointment booking is not " +
      "available for this Service, so no new appointments can enter E-Counseling."
    );
  }
  return (
    "Online counseling is enabled. New Online Counseling appointments may be scheduled where " +
    "Counselor Availability permits. Scheduled Online Counseling appointments use the " +
    "E-Counseling workspace."
  );
}

export function newECounselingAppointmentsLabel({
  online,
  bookingEnabled,
}: CounselingDeliveryState): string {
  return online && bookingEnabled
    ? "Available for scheduling, subject to Counselor Availability and booking settings"
    : "Unavailable";
}

export function counselingECounselingExplanation({
  online,
  bookingEnabled,
}: CounselingDeliveryState): string {
  if (!online) {
    return "New E-Counseling appointments are unavailable because Online counseling is not enabled for this Service.";
  }
  if (!bookingEnabled) {
    return "New E-Counseling appointments are unavailable because Appointment booking is not available for this Service.";
  }
  return "Scheduled Online Counseling appointments use the E-Counseling workspace.";
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
