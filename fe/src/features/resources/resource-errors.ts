import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";

// The backend reports every invalid Resource value with one code and every
// state conflict with another, so known messages are mapped to reader-facing
// copy; anything else falls back.
const knownMessages: Record<string, string> = {
  "title is required before publication": "Add a title before publishing this Resource.",
  "body_markdown is required before publication": "Add body text before publishing this Resource.",
  "title is too long": "The title must be 200 characters or fewer.",
  "body_markdown is too large": "The body is larger than the 50 KB limit. Shorten it and try again.",
  "audience is invalid": "Choose an audience.",
  "category is invalid": "Choose a category.",
  "kind is invalid": "Choose a Resource type.",
  "external_url is required for EXTERNAL_LINK Resources": "Enter the link address before publishing this Resource.",
  "external_url is too long": "The link address must be 2,048 characters or fewer.",
  "external_url must use http or https": "The link address must start with https:// or http://.",
  "external_url must not contain embedded credentials": "The link address must not contain a user name or password.",
  "external_url is only valid for EXTERNAL_LINK Resources": "Only External link Resources can have a link address.",
  "A validated PDF file is required before publication": "Attach a PDF file before publishing this Resource.",
  "display_order must be an integer": "Enter a whole number for the display order.",
  "display_order is outside the supported range": "Enter a smaller display order.",
  "A PDF file is required.": "Choose a PDF file to attach.",
  "Only application/pdf files are supported.": "Only PDF files can be attached.",
  "The PDF file is empty.": "The selected file is empty.",
  "The PDF file exceeds the 10 MiB limit.": "The PDF must be 10 MB or smaller.",
  "The uploaded file is not a valid PDF signature.": "The selected file is not a valid PDF.",
  "A published Resource kind cannot be changed.": "The type of a published Resource cannot be changed.",
  "Remove or replace the draft FILE Resource instead of changing kind.":
    "Remove the attached file before changing the Resource type.",
  "Files can only be attached or replaced while Resource is DRAFT.":
    "Files can only be attached or replaced while the Resource is a draft.",
  "A file can only be attached to a FILE Resource.": "Change the Resource type to File before attaching a file.",
  "Only a DRAFT FILE Resource attachment may be removed.": "The file can only be removed while the Resource is a draft.",
  "The requested Resource does not have an attached management file.": "This Resource has no attached file.",
  "The requested Resource does not have a downloadable file.": "This Resource has no attached file.",
};

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
  const message = readApiErrorMessage(error.body);
  const known = message && Object.hasOwn(knownMessages, message) ? knownMessages[message] : undefined;
  switch (readApiErrorCode(error.body)) {
    case "authentication_required":
      return "Your COMPASS session has ended. Sign in again, then retry.";
    case "permission_denied":
      return "You don’t have access to manage resources.";
    case "resource_not_found":
      return "This Resource no longer exists.";
    case "publication_consequence_review_required":
      return "Review how these changes affect the published Resource before saving.";
    case "resource_conflict":
      return known ?? "This resource changed since you opened it. Review its current status before continuing.";
    case "invalid_resource_input":
      return known ?? fallback;
    case "resource_storage_unavailable":
      return "File storage is unavailable right now. Try again in a few minutes.";
    default:
      return fallback;
  }
}
