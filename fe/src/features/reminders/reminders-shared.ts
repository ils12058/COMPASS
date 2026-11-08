import { reminderReason } from "@/features/appointments/appointment-reminders";
import {
  AppointmentReminderHistoryKind,
  AppointmentReminderTransportState,
  type AppointmentReminderUpcomingEntry,
  type AppointmentsListReminderActivityParams,
  type AppointmentsListUpcomingRemindersParams,
} from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

export type ReminderView = "upcoming" | "sent";

export function reminderView(value: string | null): ReminderView {
  return value === "sent" ? "sent" : "upcoming";
}

export function reminderPageValue(value: string | null): number {
  const parsed = Number.parseInt(value ?? "1", 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

export function reminderKindFilter(value: string | null): AppointmentReminderHistoryKind | undefined {
  return value !== null && Object.values(AppointmentReminderHistoryKind).includes(value as AppointmentReminderHistoryKind)
    ? (value as AppointmentReminderHistoryKind)
    : undefined;
}

export function reminderDeliveryFilter(value: string | null): AppointmentReminderTransportState | undefined {
  return value !== null && Object.values(AppointmentReminderTransportState).includes(value as AppointmentReminderTransportState)
    ? (value as AppointmentReminderTransportState)
    : undefined;
}

export function reminderKindLabel(kind: string | null | undefined): string {
  if (kind === AppointmentReminderHistoryKind.AUTO_24H) return "24-hour reminder";
  if (kind === AppointmentReminderHistoryKind.AUTO_3H) return "3-hour reminder";
  if (kind === AppointmentReminderHistoryKind.MANUAL) return "Manual reminder";
  return "Reminder";
}

// The next automatic reminder the scheduler will still send for this Appointment, or none.
export function nextAutomaticLabel(kind: string | null | undefined): string {
  if (kind === AppointmentReminderHistoryKind.AUTO_24H) return "24 hours before start";
  if (kind === AppointmentReminderHistoryKind.AUTO_3H) return "3 hours before start";
  return "None scheduled";
}

export function lastReminderLabel(
  entry: Pick<AppointmentReminderUpcomingEntry, "last_reminder_kind" | "last_reminder_at">,
): string {
  if (!entry.last_reminder_kind) return "No reminders yet";
  const kind = reminderKindLabel(entry.last_reminder_kind);
  return entry.last_reminder_at ? `${kind} · ${formatInstitutionalDateTime(entry.last_reminder_at)}` : kind;
}

// Whether a manual reminder can be sent now, in the same plain words the send confirmation uses.
export function manualReminderLabel(
  entry: Pick<AppointmentReminderUpcomingEntry, "manual_available" | "manual_reason">,
): string {
  return entry.manual_available ? "Ready to send" : reminderReason(entry.manual_reason);
}

export function deliveryStateLabel(state: string): string {
  if (state === AppointmentReminderTransportState.NOT_REQUESTED) return "Not requested";
  if (state === AppointmentReminderTransportState.PENDING) return "Pending";
  if (state === AppointmentReminderTransportState.SENT) return "Sent";
  if (state === AppointmentReminderTransportState.FAILED) return "Not sent";
  if (state === AppointmentReminderTransportState.CANCELLED) return "Cancelled";
  return "Unavailable";
}

export function inAppStateLabel(state: string): string {
  return state === "CREATED" ? "Created" : "Not created";
}

export function reminderIssuerLabel(issuedBy: { display_name: string } | null): string {
  return issuedBy ? `Sent by ${issuedBy.display_name}` : "Sent automatically";
}

export type UpcomingReminderFilters = {
  from: string;
  to: string;
  counselor: string;
  available?: boolean;
};

export type ActivityReminderFilters = {
  from: string;
  to: string;
  kind?: AppointmentReminderHistoryKind;
  delivery?: AppointmentReminderTransportState;
};

export const REMINDER_PAGE_SIZE = 20;
// The bulk sender accepts at most 25 Appointments in one confirmation.
export const MAX_REMINDER_SELECTION = 25;

export function upcomingReminderParams(
  filters: UpcomingReminderFilters,
  page: number,
  ordering?: string,
): AppointmentsListUpcomingRemindersParams {
  return {
    ...(filters.from ? { from_date: filters.from } : {}),
    ...(filters.to ? { to_date: filters.to } : {}),
    ...(filters.counselor ? { provider_id: filters.counselor } : {}),
    ...(filters.available !== undefined ? { manual_available: filters.available } : {}),
    ...(ordering ? { ordering: ordering as AppointmentsListUpcomingRemindersParams["ordering"] } : {}),
    page,
    page_size: REMINDER_PAGE_SIZE,
  };
}

export function activityReminderParams(
  filters: ActivityReminderFilters,
  page: number,
): AppointmentsListReminderActivityParams {
  return {
    ...(filters.kind ? { kind: filters.kind } : {}),
    ...(filters.delivery ? { delivery: filters.delivery } : {}),
    ...(filters.from ? { from_date: filters.from } : {}),
    ...(filters.to ? { to_date: filters.to } : {}),
    page,
    page_size: REMINDER_PAGE_SIZE,
  };
}
