import type { TicketOutcome } from "@/features/realtime/realtime-runtime";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { realtimeIssueTicket } from "@/lib/api/generated/realtime/realtime";

// Tickets come from the ordinary same-origin API, so the session cookie and CSRF handling stay in
// the shared transport. The ticket is returned to the runtime and nowhere else: it is not cached,
// stored, or logged.
export async function requestRealtimeTicket(signal: AbortSignal): Promise<TicketOutcome> {
  try {
    const response = await realtimeIssueTicket({ signal, cache: "no-store" });
    const { ticket, user_id: userId } = response.data;
    if (typeof ticket !== "string" || typeof userId !== "string") return { kind: "unavailable" };
    return { kind: "ticket", ticket, userId };
  } catch (error) {
    if (error instanceof CompassApiError) {
      if (error.status === 401) return { kind: "session-ended" };
      if (error.status === 503 && readApiErrorCode(error.body) === "realtime_disabled") {
        return { kind: "disabled" };
      }
    }
    return { kind: "unavailable" };
  }
}
