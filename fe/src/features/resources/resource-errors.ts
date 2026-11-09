import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";

// Field issue types are stable identifiers; backend wording is never a lookup key.
const issueCopy: Record<string, string> = {
  title_text_required: "Enter a title as text.",
  title_required: "Add a title before publishing this Resource.",
  title_too_long: "Keep the title to 200 characters or fewer.",
  body_text_required: "Enter body text.",
  body_required: "Add body text before publishing this Resource.",
  body_too_large: "Keep the body to 50 KB or less.",
  external_url_text_required: "Enter a link address or leave it blank.",
  external_url_required: "Enter the link address before publishing this Resource.",
  external_url_too_long: "Keep the link address to 2,048 characters or fewer.",
  external_url_invalid: "Start the link address with https:// or http://.",
  external_url_credentials: "Use a link address without a user name or password.",
  display_order_integer_required: "Enter a whole number for the display order.",
  display_order_out_of_range: "Enter a display order between -2,147,483,648 and 2,147,483,647.",
  page_invalid: "Choose a page number of 1 or more.",
  page_size_invalid: "Choose between 1 and 50 results per page.",
  article_attachment_not_allowed: "Articles cannot have a link address or attached file.",
  external_link_file_not_allowed: "External link Resources cannot have an attached file.",
  file_external_url_not_allowed: "File Resources cannot have a link address.",
  pdf_required_for_publication: "Attach a PDF file before publishing this Resource.",
  external_url_not_allowed: "Only External link Resources can have a link address.",
  unsupported_fields: "Review the Resource details and try again.",
  pdf_required: "Choose a PDF file to attach.",
  pdf_content_type_invalid: "Choose a PDF file.",
  pdf_empty: "Choose a file that is not empty.",
  pdf_too_large: "Choose a PDF file of 10 MB or less.",
  pdf_signature_invalid: "Choose a valid PDF file.",
  resource_archived: "You can't edit an archived Resource.",
  published_kind_immutable: "You can't change the type of a published Resource.",
  attached_file_kind_immutable: "Remove or replace this draft Resource to use a different type.",
  file_attachment_requires_draft: "You can attach or replace a file only while the Resource is a draft.",
  file_attachment_requires_file_kind: "Choose the File Resource type before attaching a file.",
  file_attachment_changed: "This Resource changed. Review its type and status before attaching a file.",
  management_file_missing: "This Resource has no attached file.",
  file_removal_requires_draft_file: "You can remove a file only from a draft File Resource.",
  publication_requires_draft: "You can publish only a draft Resource.",
  resource_already_archived: "This Resource is already archived.",
  download_file_missing: "This Resource has no attached file.",
  ordering_invalid: "Choose a Resource order.",
  audience_invalid: "Choose an audience.",
  category_invalid: "Choose a category.",
  kind_invalid: "Choose a Resource type.",
  status_invalid: "Choose a Resource status.",
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

export function resourceErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}

export function isUncertainResourceMutation(error: unknown): boolean {
  return !(error instanceof CompassApiError) || error.status >= 500;
}

export function shouldHideResourceData(error: unknown): boolean {
  return error instanceof CompassApiError && [401, 403, 404].includes(error.status);
}

export function resourceErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const identifier = issueIdentifier(error.body);
  const known = identifier && Object.hasOwn(issueCopy, identifier) ? issueCopy[identifier] : undefined;
  switch (readApiErrorCode(error.body)) {
    case "authentication_required":
      return "Your COMPASS session has ended. Sign in again, then retry.";
    case "permission_denied":
      return "You don't have permission to manage Resources.";
    case "resource_not_found":
      return "This Resource no longer exists.";
    case "publication_consequence_review_required":
      return "Review how these changes affect the published Resource before saving.";
    case "resource_conflict":
      return known ?? "Review this Resource’s type and status before continuing.";
    case "invalid_resource_input":
      return known ?? fallback;
    case "resource_storage_unavailable":
      return "Couldn't access file storage. Try again in a few minutes.";
    default:
      return fallback;
  }
}
