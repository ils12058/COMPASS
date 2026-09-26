import {
  CompassApiError,
  readApiErrorCode,
  readApiErrorMessage,
} from "@/lib/api/errors";

// Privacy Governance conflicts share one error code, so the stable backend
// messages identify the specific rule that was hit.
export const privacyConflictMessages = {
  retiredPolicyAssignment: "retired retention policy cannot be assigned",
  policyInUse: "active processing activities must be reassigned before retirement",
  noticeDraftExists: "privacy notice already has a draft",
  revisionNotEditable: "only a draft of an active privacy notice can be edited",
  revisionNotPublishable: "only a draft of an active notice can be published",
  futureEffectiveDate: "notice effective date must be today or earlier",
  noticeNotCurrent: "notice revision is no longer current; refresh notices",
} as const;

const conflictCopy: Record<string, string> = {
  [privacyConflictMessages.retiredPolicyAssignment]:
    "This Retention Policy is retired and cannot be assigned to an active Processing Activity.",
  [privacyConflictMessages.policyInUse]:
    "This Retention Policy is still assigned to an active Processing Activity and cannot be retired yet.",
  [privacyConflictMessages.noticeDraftExists]:
    "This Privacy Notice already has a draft revision. Open the existing draft instead.",
  [privacyConflictMessages.revisionNotEditable]:
    "Published and historical revisions cannot be edited. Create a new revision instead.",
  [privacyConflictMessages.revisionNotPublishable]:
    "Only a draft revision of an active Privacy Notice can be published.",
  [privacyConflictMessages.futureEffectiveDate]:
    "This revision cannot be published before its effective date. Set an effective date of today or earlier to publish it.",
  [privacyConflictMessages.noticeNotCurrent]:
    "This notice changed while you were viewing it. Refresh to review the current revision.",
  "notice revision does not require acknowledgment":
    "This notice does not ask for acknowledgment.",
  "notice revision is not applicable to this account":
    "This notice does not apply to your account.",
  "retired privacy notice cannot be edited": "Retired Privacy Notices cannot be edited.",
  "retired privacy notice cannot receive revisions":
    "Retired Privacy Notices cannot receive new revisions.",
  "retired retention policy cannot be edited": "Retired Retention Policies cannot be edited.",
  "resolved privacy reviews cannot be edited": "Resolved reviews cannot be edited.",
  "privacy review is already resolved": "This review is already resolved.",
  "use the resolve operation to resolve a privacy incident":
    "Use Resolve incident to resolve this incident.",
  "privacy incident status cannot move backward":
    "An incident cannot move back to an earlier status.",
  "resolved privacy incidents cannot be edited": "Resolved incidents cannot be edited.",
  "privacy incident is already resolved": "This incident is already resolved.",
  "processing activity code already exists":
    "A Processing Activity with this code already exists. Use a different code.",
  "retention policy code already exists":
    "A Retention Policy with this code already exists. Use a different code.",
  "privacy notice code already exists":
    "A Privacy Notice with this code already exists. Use a different code.",
};

const inputCopy: Record<string, string> = {
  "code must contain only uppercase letters, digits, dot, underscore, or hyphen":
    "Code must be 2–64 characters, start with a letter or digit, and use only letters, digits, dots, underscores, or hyphens.",
  "audiences must be a nonempty bounded list": "Select at least one audience.",
  "estimated_affected_subjects must be a nonnegative integer":
    "Estimated affected people must be a whole number of zero or more.",
};

const notFoundCopy: Record<string, string> = {
  "retention policy was not found": "The selected Retention Policy is no longer available.",
  "processing activity was not found": "This Processing Activity is no longer available.",
  "privacy review was not found": "This review is no longer available.",
  "privacy notice was not found": "This Privacy Notice is no longer available.",
  "privacy notice revision was not found": "This notice revision is no longer available.",
  "privacy incident was not found": "This privacy incident is no longer available.",
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

  switch (code) {
    case "recent_mfa_required":
      return "Recent authenticator verification is required.";
    case "permission_denied":
      return "Your current access does not allow this Privacy Governance action.";
    case "privacy_record_not_found":
      return notFoundCopy[message] ?? "This privacy record is no longer available.";
    case "privacy_governance_conflict":
      return conflictCopy[message] ?? (message ? sentence(message) : fallback);
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

export function isPrivacyConflict(error: unknown, backendMessage: string): boolean {
  return (
    error instanceof CompassApiError &&
    readApiErrorCode(error.body) === "privacy_governance_conflict" &&
    readApiErrorMessage(error.body) === backendMessage
  );
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
