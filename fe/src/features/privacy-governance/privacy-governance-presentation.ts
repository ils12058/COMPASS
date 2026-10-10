import {
  AudienceValue,
  type PrivacyActivityCategory,
  type RevisionStatusValue,
} from "@/lib/api/generated/model";
import { formatDateOnly } from "@/lib/institutional-time";

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

export function formatLongDate(value: string): string {
  return formatDateOnly(value, { dateStyle: "long" });
}
