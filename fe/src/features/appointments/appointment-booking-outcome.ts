import { isSlotTakenError, SLOT_JUST_TAKEN } from "@/features/appointments/appointment-slot-freshness";
import {
  appointmentErrorCode,
  appointmentErrorMessage,
  deliveryModeLabel,
  formatAppointmentDateTime,
} from "@/features/appointments/appointments-shared";
import { CompassApiError } from "@/lib/api/errors";
import type { AppointmentResponse } from "@/lib/api/generated/model";

// Where a failed booking is shown: at the step that can resolve it, never below the whole sheet.
//  - "time": the chosen time was taken; the times reload and the reader picks another.
//  - "service": the Service stopped being bookable; the choice resets and the Services reload.
//  - "review": everything else, next to Book, including a response that could not be confirmed.
export type BookingFailure =
  | { step: "time"; message: string }
  | { step: "service"; message: string }
  | { step: "review"; message: string; uncertain: boolean; keepIntent: boolean };

export const BOOKING_UNCONFIRMED =
  "The booking response could not be confirmed. Retry the same booking details to check the result safely.";

export function classifyBookingFailure(caught: unknown): BookingFailure {
  const code = appointmentErrorCode(caught);
  if (isSlotTakenError(caught)) return { step: "time", message: SLOT_JUST_TAKEN };
  if (code === "appointment_not_schedulable") {
    return {
      step: "service",
      message: `${appointmentErrorMessage(caught, "This Service is not currently available for scheduling.")} Choose from the current Services.`,
    };
  }
  if (code === "idempotency_key_conflict") {
    // The previous attempt's key no longer matches; the next attempt starts a new one.
    return {
      step: "review",
      message: appointmentErrorMessage(caught, "The booking attempt could not be verified. Review the details and submit again."),
      uncertain: false,
      keepIntent: false,
    };
  }
  if (caught instanceof CompassApiError) {
    return {
      step: "review",
      message: appointmentErrorMessage(caught, "The Appointment could not be booked."),
      uncertain: false,
      keepIntent: true,
    };
  }
  // No server answer was read. Keeping the exact-intent key makes a retry replay-safe: the server
  // returns the Appointment it already made instead of booking twice.
  return { step: "review", message: BOOKING_UNCONFIRMED, uncertain: true, keepIntent: true };
}

// What the completion dialog states about a confirmed booking: only facts the Review step already
// showed, read back from the server's answer. No purpose, notes, Student details, or other record
// content.
export type BookedAppointment = {
  id: string;
  referenceCode: string;
  facts: { label: string; value: string }[];
};

export function bookedAppointmentFromResponse(
  appointment: AppointmentResponse,
  context: { assignedCounselor: boolean; timeZone?: string },
): BookedAppointment {
  const start = new Date(appointment.starts_at).getTime();
  const end = new Date(appointment.ends_at).getTime();
  const minutes = Number.isFinite(start) && Number.isFinite(end) ? Math.round((end - start) / 60_000) : null;
  return {
    id: appointment.id,
    referenceCode: appointment.reference_code,
    facts: [
      { label: "Reference", value: appointment.reference_code },
      { label: "Service", value: appointment.service.name },
      {
        label: "Counselor",
        value: appointment.provider.display_name + (context.assignedCounselor ? " · Assigned counselor" : ""),
      },
      {
        label: "Schedule",
        value: formatAppointmentDateTime(appointment.starts_at, appointment.ends_at, context.timeZone),
      },
      { label: "Delivery", value: deliveryModeLabel(appointment.delivery_mode) },
      ...(minutes !== null && minutes > 0 ? [{ label: "Duration", value: `${minutes} minutes` }] : []),
    ],
  };
}
