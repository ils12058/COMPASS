import {
  CompassApiError,
  readApiErrorCode,
  readApiErrorMessage,
} from "@/lib/api/errors";

// Stable backend conflict codes; each maps to a distinct recovery in the workspace.
export const PrivacyConflictCode = {
  codeInUse: "privacy_code_in_use",
  retentionPolicyInUse: "privacy_retention_policy_in_use",
  retentionPolicyRetired: "privacy_retention_policy_retired",
  noticeRetired: "privacy_notice_retired",
  noticeDraftExists: "privacy_notice_draft_exists",
  noticeRevisionImmutable: "privacy_notice_revision_immutable",
  noticeNotYetEffective: "privacy_notice_not_yet_effective",
  noticeRevisionNotCurrent: "privacy_notice_revision_not_current",
  acknowledgmentNotApplicable: "privacy_notice_acknowledgment_not_applicable",
  recordResolved: "privacy_record_resolved",
  incidentStatusInvalid: "privacy_incident_status_invalid",
} as const;

export type PrivacyConflictCode = (typeof PrivacyConflictCode)[keyof typeof PrivacyConflictCode];

const conflictCopy: Record<PrivacyConflictCode, string> = {
  [PrivacyConflictCode.codeInUse]: "This code is already in use. Use a different code.",
  [PrivacyConflictCode.retentionPolicyInUse]:
    "This Retention Policy is still assigned to an active Processing Activity and cannot be retired yet.",
  [PrivacyConflictCode.retentionPolicyRetired]:
    "This Retention Policy is retired. Retired policies cannot be edited or newly assigned.",
  [PrivacyConflictCode.noticeRetired]:
    "This Privacy Notice is retired, so it and its revisions can no longer be changed.",
  [PrivacyConflictCode.noticeDraftExists]:
    "This Privacy Notice already has a draft revision. Open the existing draft instead.",
  [PrivacyConflictCode.noticeRevisionImmutable]:
    "Published and historical revisions cannot be edited. Create a new revision instead.",
  [PrivacyConflictCode.noticeNotYetEffective]:
    "This revision cannot be published before its effective date. Set an effective date of today or earlier to publish it.",
  [PrivacyConflictCode.noticeRevisionNotCurrent]:
    "This notice changed while you were viewing it. Refresh to review the current revision.",
  [PrivacyConflictCode.acknowledgmentNotApplicable]:
    "This notice does not ask for your acknowledgment.",
  [PrivacyConflictCode.recordResolved]:
    "This record is already resolved and can no longer be changed.",
  [PrivacyConflictCode.incidentStatusInvalid]:
    "An incident can only move forward. Use Resolve incident to resolve it.",
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
  review_due_on: "Review due",
  policy_reference: "Policy reference",
  requires_acknowledgment: "Require acknowledgment",
};

function sentence(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return trimmed;
  const capitalized = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
  return /[.!?]$/.test(capitalized) ? capitalized : capitalized + ".";
}

function translateInput(message: string, labels: PrivacyFieldLabels): string {
  const known = inputCopy[message];
  if (known) return known;
  const match = /^([a-z_]+)(\b.*)$/.exec(message);
  if (match) {
    const label = labels[match[1]] ?? baseFieldLabels[match[1]];
    if (label) return sentence(`“${label}”${match[2]}`);
  }
  return sentence(message);
}

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
    case "recent_mfa_required":
      return "Recent authenticator verification is required.";
    case "permission_denied":
      return "Your current access does not allow this Privacy Governance action.";
    case "privacy_record_not_found":
      return "This privacy record is no longer available. Refresh and try again.";
    case "privacy_governance_conflict":
      return message ? sentence(message) : fallback;
    case "invalid_privacy_governance_input":
      return message ? translateInput(message, labels) : fallback;
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

export function isRecentMfaRequired(error: unknown): boolean {
  return (
    error instanceof CompassApiError &&
    readApiErrorCode(error.body) === "recent_mfa_required"
  );
}

export function isNotFound(error: unknown): boolean {
  return error instanceof CompassApiError && error.status === 404;
}
