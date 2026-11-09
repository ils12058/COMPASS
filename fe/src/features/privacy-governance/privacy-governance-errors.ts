import {
  CompassApiError,
  readApiErrorCode,
} from "@/lib/api/errors";

// Stable backend conflict codes; each maps to a distinct recovery in the workspace.
export const PrivacyConflictCode = {
  codeInUse: "privacy_code_in_use",
  noticeRetired: "privacy_notice_retired",
  noticeDraftExists: "privacy_notice_draft_exists",
  noticeRevisionImmutable: "privacy_notice_revision_immutable",
  noticeNotYetEffective: "privacy_notice_not_yet_effective",
  noticeRevisionNotCurrent: "privacy_notice_revision_not_current",
  noticeRevisionChanged: "privacy_notice_revision_changed",
  acknowledgmentNotApplicable: "privacy_notice_acknowledgment_not_applicable",
} as const;

export type PrivacyConflictCode = (typeof PrivacyConflictCode)[keyof typeof PrivacyConflictCode];

const conflictCopy: Record<PrivacyConflictCode, string> = {
  [PrivacyConflictCode.codeInUse]: "This code is already in use. Use a different code.",
  [PrivacyConflictCode.noticeRetired]:
    "You can't change a retired Privacy Notice or its revisions.",
  [PrivacyConflictCode.noticeDraftExists]:
    "This Privacy Notice already has a draft revision. Open it to continue.",
  [PrivacyConflictCode.noticeRevisionImmutable]:
    "You can't edit published or historical revisions. Create a new revision.",
  [PrivacyConflictCode.noticeNotYetEffective]:
    "Set an effective date of today or earlier before publishing this revision.",
  [PrivacyConflictCode.noticeRevisionNotCurrent]:
    "This notice was updated while you were viewing it. The current version is now shown.",
  [PrivacyConflictCode.noticeRevisionChanged]:
    "This draft was saved elsewhere while you were editing. Review the latest saved version before saving again.",
  [PrivacyConflictCode.acknowledgmentNotApplicable]:
    "This notice does not ask for your acknowledgment.",
};

function isPrivacyConflictCode(code: string | undefined): code is PrivacyConflictCode {
  return Object.values(PrivacyConflictCode).some((value) => value === code);
}

const inputCopy: Record<string, string> = {
  page_invalid: "Choose a page number between 1 and 100,000.",
  page_size_invalid: "Choose between 1 and 50 results per page.",
  code_invalid: "Use 2–64 letters, digits, dots, underscores or hyphens, starting with a letter or digit.",
  record_invalid: "Review the privacy record details and try again.",
  audiences_required: "Choose at least one audience and no more than three.",
  audiences_invalid: "Choose Public, Students or Staff as the audience.",
  audiences_duplicate: "Choose each audience only once.",
  acknowledgment_invalid: "Choose whether this notice requires acknowledgment.",
  effective_date_invalid: "Enter a valid effective date.",
  unsupported_revision_fields: "Review the notice revision details and try again.",
  code_required: "Enter a code.",
  code_too_long: "Keep the code to 64 characters or fewer.",
  code_text_required: "Enter the code as text.",
  name_required: "Enter a name.",
  name_too_long: "Keep the name to 160 characters or fewer.",
  name_text_required: "Enter the name as text.",
  title_required: "Enter a title.",
  title_too_long: "Keep the title to 200 characters or fewer.",
  title_text_required: "Enter the title as text.",
  summary_required: "Enter a summary.",
  summary_too_long: "Keep the summary to 2,000 characters or fewer.",
  summary_text_required: "Enter the summary as text.",
  body_required: "Enter body text.",
  body_too_long: "Keep the body to 20,000 characters or fewer.",
  body_text_required: "Enter the body as text.",
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

export type PrivacyFieldLabels = Record<string, string>;

const baseFieldLabels: PrivacyFieldLabels = {
  code: "Code",
  name: "Name",
  title: "Title",
  summary: "Summary",
  effective_on: "Effective date",
  requires_acknowledgment: "Require acknowledgment",
};

function validationField(body: unknown): string | undefined {
  if (!body || typeof body !== "object" || !("error" in body)) return undefined;
  const error = (body as { error: unknown }).error;
  if (!error || typeof error !== "object" || !("details" in error)) return undefined;
  const details = (error as { details: unknown }).details;
  if (!Array.isArray(details) || details.length === 0) return undefined;
  const issue: unknown = details[0];
  if (!issue || typeof issue !== "object" || !("loc" in issue)) return undefined;
  const location = issue.loc;
  if (!Array.isArray(location) || location.length === 0) return undefined;
  const field = location[location.length - 1];
  return typeof field === "string" ? field : undefined;
}

export function privacyErrorMessage(
  error: unknown,
  fallback: string,
  labels: PrivacyFieldLabels = {},
): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  const identifier = issueIdentifier(error.body);

  if (isPrivacyConflictCode(code)) return conflictCopy[code];
  switch (code) {
    case "permission_denied":
      return "You don't have permission to perform this privacy action.";
    case "privacy_record_not_found":
      return "Couldn't find this privacy record. Refresh and try again.";
    case "privacy_governance_conflict":
      return "Refresh this privacy record and review its details before continuing.";
    case "invalid_privacy_governance_input":
      return identifier && Object.hasOwn(inputCopy, identifier)
        ? inputCopy[identifier]
        : "Review the privacy record details and try again.";
    case "validation_error": {
      const field = validationField(error.body);
      const label = field
        ? Object.hasOwn(labels, field)
          ? labels[field]
          : Object.hasOwn(baseFieldLabels, field)
            ? baseFieldLabels[field]
            : undefined
        : undefined;
      return label
        ? `“${label}” needs attention. Check it and try again.`
        : "Review the form values and try again.";
    }
    default:
      return fallback;
  }
}

export function hasPrivacyConflictCode(error: unknown, code: PrivacyConflictCode): boolean {
  return error instanceof CompassApiError && readApiErrorCode(error.body) === code;
}
