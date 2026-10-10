import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";

const activityErrors: Record<string, string> = {
  invalid_pagination: "This activity page is unavailable. Return to the previous page or adjust the filters.",
  invalid_privacy_activity_request: "Check the activity filters and try again.",
  invalid_technical_activity_request: "Check the activity filters and try again.",
  invalid_supervised_activity_request: "Check the activity filters and try again.",
  privacy_activity_export_too_large: "More than 10,000 activity records match these filters. Narrow the date range or filters before exporting.",
  release_audit_unavailable: "The activity export cannot be released while its required privacy audit is unavailable. Try again later.",
};

export function activityErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  if (code === "permission_denied") {
    return "You don't have access to view or export this activity.";
  }
  if (code && activityErrors[code]) return activityErrors[code];
  if (code === "validation_error") {
    return "An activity filter was not accepted. Check the values and try again.";
  }
  return fallback;
}
