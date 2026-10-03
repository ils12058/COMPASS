import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";

// The backend reports every invalid Announcement value with one code, so the
// known messages are mapped to reader-facing copy; anything else falls back.
const inputMessages: Record<string, string> = {
  "title is required before publication": "Add a title before publishing this Announcement.",
  "body_markdown is required before publication": "Add body text before publishing this Announcement.",
  "title is too long": "The title must be 200 characters or fewer.",
  "body_markdown is too large": "The body is larger than the 50 KB limit. Shorten it and try again.",
  "audience is invalid": "Choose an audience.",
  "expires_at must be a timezone-aware datetime or null": "Enter a valid expiry date and time.",
  "expires_at must be in the future while the Announcement is published":
    "A published Announcement cannot have an expiry that has already passed. Choose a future time or use Archive Announcement for immediate removal.",
};

export function announcementErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}

export function isUncertainAnnouncementMutation(error: unknown): boolean {
  return !(error instanceof CompassApiError) || error.status >= 500;
}

export function shouldHideAnnouncementData(error: unknown): boolean {
  return error instanceof CompassApiError && [401, 403, 404].includes(error.status);
}

export function announcementErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const message = readApiErrorMessage(error.body);
  switch (readApiErrorCode(error.body)) {
    case "authentication_required":
      return "Your COMPASS session has ended. Sign in again, then retry.";
    case "permission_denied":
      return "Announcement management is unavailable to this account.";
    case "announcement_not_found":
      return "This Announcement no longer exists.";
    case "publication_consequence_review_required":
      return "Review how these changes affect the published Announcement before saving.";
    case "announcement_not_editable":
      return "This announcement can no longer be edited. Review its current status before continuing.";
    case "invalid_announcement_input":
      return message && Object.hasOwn(inputMessages, message) ? inputMessages[message] : fallback;
    default:
      return fallback;
  }
}
