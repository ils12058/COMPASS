import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";

export function activityErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  if (code === "permission_denied") {
    return "You cannot view or export this activity with this account.";
  }
  if (code && [
    "invalid_pagination",
    "invalid_privacy_activity_request",
    "invalid_technical_activity_request",
    "invalid_supervised_activity_request",
    "privacy_activity_export_too_large",
    "release_audit_unavailable",
  ].includes(code)) {
    return readApiErrorMessage(error.body) || fallback;
  }
  if (code === "validation_error") {
    return "An activity filter was not accepted. Check the values and try again.";
  }
  return fallback;
}
