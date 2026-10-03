"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { AppointmentStatus, DeliveryMode } from "@/lib/api/generated/model";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { INSTITUTION_TIME_ZONE } from "@/lib/institutional-time";

const statusLabels: Record<string, string> = {
  [AppointmentStatus.SCHEDULED]: "Scheduled",
  [AppointmentStatus.CANCELLED]: "Cancelled",
  [AppointmentStatus.COMPLETED]: "Completed",
  [AppointmentStatus.NO_SHOW]: "No-show",
};

const statusClasses: Record<string, string> = {
  [AppointmentStatus.SCHEDULED]: "border-info/30 bg-info/10 text-info",
  [AppointmentStatus.CANCELLED]: "border-border-strong bg-surface-muted text-muted",
  [AppointmentStatus.COMPLETED]: "border-success/30 bg-success/10 text-success",
  [AppointmentStatus.NO_SHOW]: "border-warning/30 bg-warning/10 text-warning",
};

const knownErrors: Record<string, string> = {
  current_student_required: "Only a current student can book or reschedule an appointment.",
  current_academic_year_not_configured:
    "Booking is unavailable until the current academic year is set up for this service.",
  current_inventory_required:
    "Submit your Individual Inventory for the current academic year before booking this service.",
  appointment_not_found: "This appointment is unavailable to this account.",
  invalid_appointment_request: "The Appointment request contains a value that is not accepted.",
  appointment_default_provider_unresolved:
    "A Counselor could not be resolved. Choose an eligible Counselor and try again.",
  appointment_time_unavailable: "That time is no longer available. Choose another available time.",
  appointment_time_conflict: "That time conflicts with another Appointment. Choose another available time.",
  appointment_lifecycle_conflict:
    "This appointment can no longer be changed. Refresh it to review its current status.",
  appointment_cancellation_cutoff_passed:
    "The deadline to cancel or reschedule this appointment has passed.",
  appointment_cancellation_conflict:
    "This appointment can no longer be cancelled.",
  ecounseling_access_started:
    "This Appointment can no longer be cancelled because its online counseling access period has begun.",
  ecounseling_access_open:
    "Wait until the online counseling access or rejoin period has ended before completing this Appointment or marking it as no-show.",
  ecounseling_room_linked:
    "This Appointment cannot be cancelled because an E-Counseling room is already linked.",
  appointment_not_schedulable:
    "This Service cannot currently be scheduled. Refresh the Service selection and try again.",
  idempotency_unavailable:
    "Booking could not be safely verified. Keep the same booking details and try again.",
  idempotency_key_conflict:
    "This booking attempt no longer matches its original request. Review the details and submit again.",
  permission_denied: "You do not have permission to use this Appointment action.",
  recent_mfa_required: "Recent authenticator verification is required.",
};

export function appointmentErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError
    ? readApiErrorCode(error.body)
    : undefined;
}

export function appointmentErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  if (code && knownErrors[code]) return knownErrors[code];
  return fallback;
}

export function appointmentStatusLabel(status: string): string {
  return statusLabels[status] ?? "Status unavailable";
}

export function AppointmentStatusBadge({ status }: { status: string }) {
  return (
    <span
      className={
        "inline-flex min-h-6 items-center rounded-full border px-2.5 text-xs font-semibold " +
        (statusClasses[status] ?? "border-border bg-surface-muted text-muted")
      }
    >
      {appointmentStatusLabel(status)}
    </span>
  );
}

export function deliveryModeLabel(mode: string): string {
  return mode === DeliveryMode.ONLINE ? "Online" : "In person";
}

export function formatAppointmentDateTime(
  startsAt: string,
  endsAt: string,
  timeZone?: string,
): string {
  const start = new Date(startsAt);
  const end = new Date(endsAt);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return `${startsAt}–${endsAt}`;
  }
  const zone = timeZone ?? INSTITUTION_TIME_ZONE;
  try {
    const day = new Intl.DateTimeFormat("en-PH", {
      timeZone: zone,
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(start);
    const times = new Intl.DateTimeFormat("en-PH", {
      timeZone: zone,
      hour: "numeric",
      minute: "2-digit",
    });
    return `${day} · ${times.format(start)}–${times.format(end)}`;
  } catch {
    return `${startsAt}–${endsAt}`;
  }
}

export function formatAppointmentTime(value: string, timeZone?: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  try {
    return new Intl.DateTimeFormat("en-PH", {
      timeZone: timeZone ?? INSTITUTION_TIME_ZONE,
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  } catch {
    return value;
  }
}

export function AppointmentsUnavailable({
  children = "Appointments are unavailable to this account.",
}: {
  children?: ReactNode;
}) {
  return (
    <WorkspaceUnavailable title="Appointments unavailable">
      {children}
    </WorkspaceUnavailable>
  );
}

export function AppointmentsWorkspaceGate({
  section,
  children,
}: {
  section: "self" | "manage" | "book";
  children: ReactNode;
}) {
  const { user } = usePortalSession();
  const access = getAppointmentAccess(user);
  const allowed =
    section === "self"
      ? access.canViewSelf
      : section === "manage"
        ? access.canManage
        : access.canBook;

  if (!allowed) {
    return (
      <AppointmentsUnavailable>
        {section === "book" && access.isStudent
          ? access.canViewSelf
            ? "Only current students can book appointments. You can still view your existing appointments."
            : "Booking is unavailable to this account."
          : "This appointment page is unavailable to this account."}
      </AppointmentsUnavailable>
    );
  }
  return children;
}

export function AppointmentsLocalNavigation() {
  const { user } = usePortalSession();
  const pathname = usePathname();
  const access = getAppointmentAccess(user);
  const links = [
    ...(access.canViewSelf
      ? [{ href: "/portal/appointments/my", label: "My appointments" }]
      : []),
    ...(access.canBook
      ? [{ href: "/portal/appointments/book", label: "Book appointment" }]
      : []),
    ...(access.canManage
      ? [{ href: "/portal/appointments/manage", label: "Manage appointments" }]
      : []),
  ];

  if (links.length === 0) return null;
  return (
    <nav aria-label="Appointment navigation" className="mb-7 flex flex-wrap gap-x-5 gap-y-2 border-b border-border">
      {links.map((link) => {
        const current = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={current ? "page" : undefined}
            className={
              "inline-flex min-h-11 items-center border-b-2 px-1 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus " +
              (current
                ? "border-brand text-brand"
                : "border-transparent text-muted hover:text-ink")
            }
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function AppointmentListSkeleton() {
  return (
    <LoadingRegion label="Loading Appointments…" className="space-y-3 py-4">
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
    </LoadingRegion>
  );
}

export function AppointmentDetailSkeleton() {
  return (
    <>
      <AppointmentsLocalNavigation />
      <LoadingRegion label="Loading Appointment details…">
        <Skeleton className="h-9 w-2/5" />
        <Skeleton className="mt-5 h-24 w-full" />
        <Skeleton className="mt-5 h-48 w-full" />
      </LoadingRegion>
    </>
  );
}

export function AppointmentsPageHeading({
  title,
  description,
  action,
  headingId = "appointments-page-heading",
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  headingId?: string;
}) {
  return (
    <div className="mb-7 flex flex-col gap-3 border-b border-border pb-5 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 id={headingId} className="font-heading text-3xl font-bold text-ink">{title}</h1>
        {description ? (
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

// A list view rather than an Appointment status: Scheduled and not yet started by COMPASS
// server time. It is the population the Overview counts as upcoming.
export const UPCOMING_APPOINTMENTS_VIEW = "UPCOMING";

export function updateAppointmentQuery(
  pathname: string,
  current: URLSearchParams,
  updates: Record<string, string>,
  resetPage = true,
): string {
  const next = new URLSearchParams(current.toString());
  for (const [key, value] of Object.entries(updates)) {
    if (value) next.set(key, value);
    else next.delete(key);
  }
  if (resetPage) next.delete("page");
  const query = next.toString();
  return query ? `${pathname}?${query}` : pathname;
}
