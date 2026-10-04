import {
  CompassApiError,
  readApiErrorCode,
  readApiErrorMessage,
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
    "This Privacy Notice is retired, so it and its revisions can no longer be changed.",
  [PrivacyConflictCode.noticeDraftExists]:
    "This Privacy Notice already has a draft revision. Open the existing draft instead.",
  [PrivacyConflictCode.noticeRevisionImmutable]:
    "Published and historical revisions cannot be edited. Create a new revision instead.",
  [PrivacyConflictCode.noticeNotYetEffective]:
    "This revision cannot be published before its effective date. Set an effective date of today or earlier to publish it.",
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
  "code must contain only uppercase letters, digits, dot, underscore, or hyphen":
    "Code must be 2–64 characters, start with a letter or digit, and use only letters, digits, dots, underscores, or hyphens.",
  "audiences must be a nonempty bounded list": "Select at least one audience.",
  "estimated_affected_subjects must be a nonnegative integer":
    "Estimated affected people must be a whole number of zero or more.",
};

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
  const location = (details[0] as { loc?: unknown }).loc;
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
  const message = readApiErrorMessage(error.body) ?? "";

  if (isPrivacyConflictCode(code)) return conflictCopy[code];
  switch (code) {
    case "permission_denied":
      return "You cannot complete this privacy action with this account.";
    case "privacy_record_not_found":
      return "This privacy record is no longer available. Refresh and try again.";
    case "privacy_governance_conflict":
      return "This privacy record changed before the action completed. Refresh it and review its current state.";
    case "invalid_privacy_governance_input":
      return Object.hasOwn(inputCopy, message)
        ? inputCopy[message]
        : "Some privacy record details were not accepted. Review them and try again.";
    case "validation_error": {
      const field = validationField(error.body);
      const label = field ? labels[field] ?? baseFieldLabels[field] : undefined;
      return label
        ? `“${label}” was not accepted. Check it and try again.`
        : "Some values were not accepted. Review the form and try again.";
    }
    default:
      return fallback;
  }
}

export function hasPrivacyConflictCode(error: unknown, code: PrivacyConflictCode): boolean {
  return error instanceof CompassApiError && readApiErrorCode(error.body) === code;
}

export function isNotFound(error: unknown): boolean {
  return error instanceof CompassApiError && error.status === 404;
}
