"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { AppointmentListOrdering, AppointmentStatus, DeliveryMode } from "@/lib/api/generated/model";
import type { SortOption } from "@/components/ui/sort-field";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { INSTITUTION_TIME_ZONE } from "@/lib/institutional-time";
import { PageHeader } from "@/components/ui/page-header";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { WorkspaceTabs, workspaceTabClass } from "@/components/ui/workspace-tabs";

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
  current_student_required: "Only a current Student can book or reschedule an Appointment.",
  current_academic_year_not_configured:
    "The Guidance Office must set up the current Academic Year before you can book this Service.",
  current_inventory_required:
    "Submit your Individual Inventory for the current Academic Year before booking this Service.",
  appointment_not_found: "You can't open this Appointment.",
  invalid_appointment_request: "Some Appointment details need attention. Review them and try again.",
  appointment_default_provider_unresolved:
    "Couldn't select a Counselor. Choose a listed Counselor and try again.",
  appointment_default_provider_not_qualified:
    "Your default Counselor does not provide this Service. Choose one of the listed Counselors.",
  appointment_time_unavailable: "That time was just taken. Choose another available time.",
  appointment_time_conflict: "That time was just taken. Choose another available time.",
  appointment_lifecycle_conflict:
    "This Appointment was updated before your action completed.",
  appointment_cancellation_cutoff_passed:
    "The deadline to cancel or reschedule this Appointment has passed.",
  appointment_cancellation_conflict:
    "This Appointment can no longer be cancelled.",
  ecounseling_access_started:
    "You can no longer cancel this Appointment because the E-Counseling session has started.",
  ecounseling_access_open:
    "Wait until the E-Counseling session and rejoin period have ended before completing this Appointment or marking it as no-show.",
  ecounseling_room_linked:
    "This Appointment cannot be cancelled because an E-Counseling room is already linked.",
  appointment_not_schedulable:
    "This Service is not currently available for scheduling.",
  idempotency_unavailable:
    "Couldn't verify your booking. Keep the same details and try again.",
  idempotency_key_conflict:
    "This booking attempt no longer matches its original details. Review them and submit again.",
  permission_denied: "You can't perform this Appointment action.",
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
  return statusLabels[status] ?? "Status not shown";
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

// Start time is the one Appointment ordering. Scheduled lists default to the earliest start and
// history to the latest; the backend reports which one it applied (ADR-090).
export const appointmentOrderingOptions: readonly SortOption<AppointmentListOrdering>[] = [
  { value: AppointmentListOrdering.EARLIEST_START, label: "Earliest start first" },
  { value: AppointmentListOrdering.LATEST_START, label: "Latest start first" },
];

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
  children = "You don't have access to Appointments.",
}: {
  children?: ReactNode;
}) {
  return (
    <WorkspaceUnavailable title="Appointment access">
      {children}
    </WorkspaceUnavailable>
  );
}

export function AppointmentsLocalNavigation() {
  const { user } = usePortalSession();
  const pathname = usePathname();
  const access = getAppointmentAccess(user);
  const links = [
    ...(access.canViewSelf
      ? [{ href: "/portal/appointments/my", label: "My Appointments" }]
      : []),
    ...(access.canBook
      ? [{ href: "/portal/appointments/book", label: "Book Appointment" }]
      : []),
    ...(access.canManage
      ? [{ href: "/portal/appointments/manage", label: "Manage Appointments" }]
      : []),
    ...(access.canManageSlots
      ? [{ href: "/portal/appointments/slots", label: "Manage Appointment slots" }]
      : []),
  ];

  if (links.length === 0) return null;
  return (
    <WorkspaceTabs label="Appointment navigation">
      {links.map((link) => {
        const current = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={current ? "page" : undefined}
            className={workspaceTabClass(current)}
          >
            {link.label}
          </Link>
        );
      })}
    </WorkspaceTabs>
  );
}

export function AppointmentListSkeleton({ framed = true }: { framed?: boolean }) {
  return <RowsSkeleton label="Loading Appointments…" framed={framed} />;
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
  help,
  context,
  meta,
  children,
  headingId = "appointments-page-heading",
}: {
  title: ReactNode;
  description?: string;
  action?: ReactNode;
  help?: ReactNode;
  context?: ReactNode;
  meta?: ReactNode;
  children?: ReactNode;
  headingId?: string;
}) {
  return (
    <PageHeader title={title} headingId={headingId} description={description} actions={action} help={help} context={context} meta={meta}>
      {children}
    </PageHeader>
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
