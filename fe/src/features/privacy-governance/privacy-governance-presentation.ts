import {
  AudienceValue,
  RetentionRecordCategoryValue,
  type PrivacyActivityCategory,
  type RevisionStatusValue,
} from "@/lib/api/generated/model";

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

export const retentionRecordCategoryLabels: Record<
  RetentionRecordCategoryValue,
  string
> = {
  INDIVIDUAL_INVENTORY: "Individual Inventory",
  COUNSELING: "Counseling records",
  ROUTINE_INTERVIEW: "Routine Interview records",
  REFERRAL: "Referral records",
  CALL_SLIP: "Call Slip records",
  GOOD_MORAL: "Good Moral requests and issuance records",
  EXIT_INTERVIEW: "Exit Interview records",
  GRADUATE_TRACER: "Graduate Tracer responses",
  CUSTOMER_FEEDBACK: "Customer Feedback / CSM records",
};

export const retentionRecordCategoryOrder: RetentionRecordCategoryValue[] = [
  RetentionRecordCategoryValue.INDIVIDUAL_INVENTORY,
  RetentionRecordCategoryValue.COUNSELING,
  RetentionRecordCategoryValue.ROUTINE_INTERVIEW,
  RetentionRecordCategoryValue.REFERRAL,
  RetentionRecordCategoryValue.CALL_SLIP,
  RetentionRecordCategoryValue.GOOD_MORAL,
  RetentionRecordCategoryValue.EXIT_INTERVIEW,
  RetentionRecordCategoryValue.GRADUATE_TRACER,
  RetentionRecordCategoryValue.CUSTOMER_FEEDBACK,
];

export function formatLongDate(value: string): string {
  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "long" }).format(date);
}
