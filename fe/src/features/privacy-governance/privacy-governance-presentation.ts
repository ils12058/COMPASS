import {
  AudienceValue,
  IncidentStatusValue,
  type NotificationAssessmentValue,
  type PrivacyActivityCategory,
  type ReviewStatusValue,
  type ReviewTypeValue,
  type RevisionStatusValue,
} from "@/lib/api/generated/model";

export const reviewTypeTitles: Record<ReviewTypeValue, string> = {
  PRIVACY_REVIEW: "Privacy review",
  PIA: "Privacy impact assessment",
};

export const reviewTypeOptionLabels: Record<ReviewTypeValue, string> = {
  PRIVACY_REVIEW: "Privacy review",
  PIA: "Privacy impact assessment (PIA)",
};

export const reviewTypeShortLabels: Record<ReviewTypeValue, string> = {
  PRIVACY_REVIEW: "Privacy review",
  PIA: "PIA",
};

export const reviewStatusLabels: Record<ReviewStatusValue, string> = {
  OPEN: "Open",
  RESOLVED: "Resolved",
};

export const incidentStatusLabels: Record<IncidentStatusValue, string> = {
  OPEN: "Open",
  ASSESSING: "Assessing",
  CONTAINED: "Contained",
  RESOLVED: "Resolved",
};

// Human-entered governance assessment; not a legal determination.
export const notificationAssessmentLabels: Record<
  NotificationAssessmentValue,
  string
> = {
  NOT_ASSESSED: "Not assessed",
  NOT_REQUIRED: "Not required",
  REQUIRED: "Required",
  COMPLETED: "Completed",
};

export const revisionStatusLabels: Record<RevisionStatusValue, string> = {
  DRAFT: "Draft",
  PUBLISHED: "Published",
  SUPERSEDED: "Superseded",
};

export const audienceLabels: Record<AudienceValue, string> = {
  PUBLIC: "Public",
  STUDENT: "Students",
  STAFF: "Staff",
};

export const audienceDescriptions: Record<AudienceValue, string> = {
  PUBLIC: "Anyone, including people who are not signed in.",
  STUDENT: "Signed-in Student accounts.",
  STAFF: "Signed-in accounts that are not Student accounts.",
};

export const audienceOrder: AudienceValue[] = [
  AudienceValue.PUBLIC,
  AudienceValue.STUDENT,
  AudienceValue.STAFF,
];

export function audienceSummary(audiences: readonly AudienceValue[]): string {
  return audienceOrder
    .filter((audience) => audiences.includes(audience))
    .map((audience) => audienceLabels[audience])
    .join(", ");
}

export const activityCategoryLabels: Record<PrivacyActivityCategory, string> = {
  DATA_RELEASE: "Data releases",
  ACCESS_CONTROL: "Access control",
  ACCOUNT_SECURITY: "Account security",
  PRIVACY_GOVERNANCE: "Privacy governance",
};

const incidentStatusOrder: IncidentStatusValue[] = [
  IncidentStatusValue.OPEN,
  IncidentStatusValue.ASSESSING,
  IncidentStatusValue.CONTAINED,
];

// The backend only moves incidents forward and resolves them through the
// dedicated resolve operation, so the edit form offers the current status and
// later non-resolved stages only.
export function editableIncidentStatuses(
  current: IncidentStatusValue,
): IncidentStatusValue[] {
  const index = incidentStatusOrder.indexOf(current);
  return index === -1 ? [] : incidentStatusOrder.slice(index);
}

export function formatLongDate(value: string): string {
  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "long" }).format(date);
}
