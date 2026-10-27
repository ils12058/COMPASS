import { CompassApiError } from "@/lib/api/errors";

// Only a successful read of a matching active registration proves this group's outcome.
export function hasActiveRegistrationForSession(
  rows: readonly { session_id: string; status: string }[],
  sessionId: string,
): boolean {
  return rows.some(row => row.session_id === sessionId && row.status === "REGISTERED");
}

// An unread response or server failure may follow a committed mutation.
export function bookingResultIsUncertain(error: unknown): boolean {
  return !(error instanceof CompassApiError) || error.status === 408 || error.status >= 500;
}

// Student scheduling projections are account- and authorization-specific.
export function studentSchedulingScope(user: { id: string; student_lifecycle_status: string | null; capabilities: readonly string[] }): string {
  return JSON.stringify([user.id, user.student_lifecycle_status, [...user.capabilities].sort()]);
}
