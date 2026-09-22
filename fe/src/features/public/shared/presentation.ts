import {
  ResourceCategoryValue,
  ResourceKindValue,
  type ResourceCategoryValue as ResourceCategory,
  type ResourceKindValue as ResourceKind,
} from "@/lib/api/generated/model";

const publicDateFormatter = new Intl.DateTimeFormat("en-PH", {
  day: "numeric",
  month: "long",
  timeZone: "Asia/Manila",
  year: "numeric",
});

export const resourceCategoryLabels: Record<ResourceCategory, string> = {
  [ResourceCategoryValue.GENERAL]: "General",
  [ResourceCategoryValue.COUNSELING]: "Counseling",
  [ResourceCategoryValue.MENTAL_HEALTH]: "Mental health",
  [ResourceCategoryValue.ACADEMIC_SUPPORT]: "Academic support",
  [ResourceCategoryValue.CAREER]: "Career",
  [ResourceCategoryValue.WELLNESS]: "Wellness",
  [ResourceCategoryValue.FORMS_AND_GUIDES]: "Forms and guides",
  [ResourceCategoryValue.OTHER]: "Other",
};

export const resourceKindLabels: Record<ResourceKind, string> = {
  [ResourceKindValue.ARTICLE]: "Article",
  [ResourceKindValue.EXTERNAL_LINK]: "External resource",
  [ResourceKindValue.FILE]: "File",
};

export function formatPublicDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : publicDateFormatter.format(date);
}

export function getSafeHttpUrl(value: string | null | undefined): string | null {
  if (!value) return null;

  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

export function isResourceCategory(value: string | undefined): value is ResourceCategory {
  return Object.values(ResourceCategoryValue).some((category) => category === value);
}

export function isResourceKind(value: string | undefined): value is ResourceKind {
  return Object.values(ResourceKindValue).some((kind) => kind === value);
}
