"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { AppointmentStatus, DeliveryMode } from "@/lib/api/generated/model";
import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";

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
    "Booking for this Service cannot continue because the current Academic Year required for the Inventory prerequisite is not configured.",
  current_inventory_required:
    "A submitted Individual Inventory for the current Academic Year is required to book this Service.",
  appointment_not_found: "This Appointment is not available within your current access.",
  invalid_appointment_request: "The Appointment request contains a value that is not accepted.",
  appointment_default_provider_unresolved:
    "A Counselor could not be resolved. Choose an eligible Counselor and try again.",
  appointment_time_unavailable: "That time is no longer available. Choose another available time.",
  appointment_time_conflict: "That time conflicts with another Appointment. Choose another available time.",
  appointment_lifecycle_conflict:
    "This Appointment can no longer be changed in the requested way.",
  appointment_cancellation_cutoff_passed:
    "The self-service cancellation or rescheduling cutoff has passed.",
  appointment_cancellation_conflict:
    "This Appointment cannot be cancelled in its current state.",
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
  return readApiErrorMessage(error.body) ?? fallback;
}

export function appointmentStatusLabel(status: string): string {
  return statusLabels[status] ?? status;
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
  const zoneOptions = timeZone ? { timeZone } : {};
  try {
    const day = new Intl.DateTimeFormat("en-PH", {
      ...zoneOptions,
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(start);
    const times = new Intl.DateTimeFormat("en-PH", {
      ...zoneOptions,
      hour: "numeric",
      minute: "2-digit",
    });
    return `${day} · ${times.format(start)}–${times.format(end)}`;
  } catch {
    return `${start.toLocaleString()}–${end.toLocaleTimeString()}`;
  }
}

export function formatAppointmentTime(value: string, timeZone?: string): string {
  const date = new Date(value);
  try {
    return new Intl.DateTimeFormat("en-PH", {
      ...(timeZone ? { timeZone } : {}),
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  } catch {
    return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
}

export function AppointmentsUnavailable({
  children = "Your current access does not include an Appointment workspace.",
}: {
  children?: ReactNode;
}) {
  return (
    <section className="max-w-xl border-y border-border py-8">
      <h1 className="font-heading text-3xl font-bold text-ink">
        Appointments unavailable
      </h1>
      <p className="mt-3 text-sm leading-6 text-muted">{children}</p>
      <Link
        href="/portal"
        className="mt-5 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        Return to Home
      </Link>
    </section>
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
          ? "Only a current Student with Appointment self-management access can book. You can still view existing Appointments from My Appointments."
          : "Your current access does not include this Appointment workspace."}
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

export function PaginationControls({
  page,
  hasNext,
  onPrevious,
  onNext,
}: {
  page: number;
  hasNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <nav aria-label="Appointment pages" className="flex items-center justify-between gap-3 border-t border-border py-4">
      <p className="text-sm text-muted">Page {page}</p>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={page <= 1} onClick={onPrevious}>
          Previous
        </Button>
        <Button variant="secondary" disabled={!hasNext} onClick={onNext}>
          Next
        </Button>
      </div>
    </nav>
  );
}

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
