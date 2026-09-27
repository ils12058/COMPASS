import {
  AnnouncementAudienceValue,
  AnnouncementStatusValue,
  type ResourceAudienceValue,
  type ResourceStatusValue,
} from "@/lib/api/generated/model";

// Announcements and Resources share the backend publication status and
// audience vocabularies; each keeps its own generated enum.
export type PublicationStatus = AnnouncementStatusValue | ResourceStatusValue;
export type PublicationAudience = AnnouncementAudienceValue | ResourceAudienceValue;

export const publicationStatusOrder: PublicationStatus[] = Object.values(AnnouncementStatusValue);
export const publicationAudienceOrder: PublicationAudience[] = Object.values(AnnouncementAudienceValue);

export const publicationStatusLabels: Record<PublicationStatus, string> = {
  [AnnouncementStatusValue.DRAFT]: "Draft",
  [AnnouncementStatusValue.PUBLISHED]: "Published",
  [AnnouncementStatusValue.ARCHIVED]: "Archived",
};

export const publicationAudienceLabels: Record<PublicationAudience, string> = {
  [AnnouncementAudienceValue.PUBLIC]: "Public",
  [AnnouncementAudienceValue.ALL_AUTHENTICATED]: "All signed-in users",
  [AnnouncementAudienceValue.STUDENTS]: "Students",
  [AnnouncementAudienceValue.GCO_PERSONNEL]: "GCO personnel",
};

export const publicationAudienceDescriptions: Record<PublicationAudience, string> = {
  [AnnouncementAudienceValue.PUBLIC]: "Anyone, including visitors who are not signed in.",
  [AnnouncementAudienceValue.ALL_AUTHENTICATED]: "Anyone signed in to COMPASS.",
  [AnnouncementAudienceValue.STUDENTS]: "Signed-in Students.",
  [AnnouncementAudienceValue.GCO_PERSONNEL]: "Signed-in Counselors and Guidance Services Staff.",
};

// Completes consequence copy such as "It will be visible to …".
export const publicationAudienceReaders: Record<PublicationAudience, string> = {
  [AnnouncementAudienceValue.PUBLIC]: "everyone, including visitors who are not signed in",
  [AnnouncementAudienceValue.ALL_AUTHENTICATED]: "everyone signed in to COMPASS",
  [AnnouncementAudienceValue.STUDENTS]: "signed-in Students",
  [AnnouncementAudienceValue.GCO_PERSONNEL]: "signed-in Counselors and Guidance Services Staff",
};

export function isPublicationStatus(value: string | null): value is PublicationStatus {
  return value !== null && publicationStatusOrder.some((status) => status === value);
}

export function isPublicationAudience(value: string | null): value is PublicationAudience {
  return value !== null && publicationAudienceOrder.some((audience) => audience === value);
}

export function displayTitle(title: string, fallback: string): string {
  return title.trim() || fallback;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
