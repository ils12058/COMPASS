import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";

// Field issue types are stable identifiers; backend wording is never a lookup key.
const issueCopy: Record<string, string> = {
  title_text_required: "Enter a title as text.",
  title_required: "Add a title before publishing this Announcement.",
  title_too_long: "Keep the title to 200 characters or fewer.",
  body_text_required: "Enter body text.",
  body_required: "Add body text before publishing this Announcement.",
  body_too_large: "Keep the body to 50 KB or less.",
  page_invalid: "Choose a page number of 1 or more.",
  page_size_invalid: "Choose between 1 and 50 results per page.",
  unsupported_fields: "Review the Announcement details and try again.",
  ordering_invalid: "Choose an Announcement order.",
  audience_invalid: "Choose an audience.",
  expiry_invalid: "Enter a valid expiry date and time.",
  expiry_not_future: "Choose a future expiry time, or archive this Announcement to remove it now.",
  status_invalid: "Choose an Announcement status.",
  pin_invalid: "Choose whether to pin this Announcement.",
  announcement_archived: "You can't edit an archived Announcement.",
  publication_requires_draft: "You can publish only a draft Announcement.",
  announcement_already_archived: "This Announcement is already archived.",
};

function issueIdentifier(body: unknown): string | undefined {
  if (!body || typeof body !== "object" || !("error" in body)) return undefined;
  const error = body.error;
  if (!error || typeof error !== "object" || !("details" in error)) return undefined;
  const details = error.details;
  if (!Array.isArray(details) || details.length === 0) return undefined;
  const issue: unknown = details[0];
  if (!issue || typeof issue !== "object" || !("type" in issue)) return undefined;
  return typeof issue.type === "string" ? issue.type : undefined;
}

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
  const identifier = issueIdentifier(error.body);
  const known = identifier && Object.hasOwn(issueCopy, identifier) ? issueCopy[identifier] : undefined;
  switch (readApiErrorCode(error.body)) {
    case "authentication_required":
      return "Your COMPASS session has ended. Sign in again, then retry.";
    case "permission_denied":
      return "You don't have permission to manage Announcements.";
    case "announcement_not_found":
      return "This Announcement no longer exists.";
    case "publication_consequence_review_required":
      return "Review how these changes affect the published Announcement before saving.";
    case "announcement_not_editable":
      return known ?? "Review this Announcement’s status before continuing.";
    case "invalid_announcement_input":
      return known ?? fallback;
    default:
      return fallback;
  }
}
