import {
  ResourceCategoryValue,
  ResourceKindValue,
  type ResourceCategoryValue as ResourceCategory,
  type ResourceKindValue as ResourceKind,
} from "@/lib/api/generated/model";
import { INSTITUTION_TIME_ZONE } from "@/lib/institutional-time";

const publicDateFormatter = new Intl.DateTimeFormat("en-PH", {
  day: "numeric",
  month: "long",
  timeZone: INSTITUTION_TIME_ZONE,
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

const publicDatePartsFormatter = new Intl.DateTimeFormat("en-PH", {
  day: "numeric",
  month: "short",
  timeZone: INSTITUTION_TIME_ZONE,
  year: "numeric",
});

export function formatPublicDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : publicDateFormatter.format(date);
}

export function publicDateParts(value: string): { day: string; month: string; year: string } | null {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;

  const parts = publicDatePartsFormatter.formatToParts(date);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? "";
  return { day: part("day"), month: part("month"), year: part("year") };
}

const PREVIEW_MAX_LENGTH = 240;

// A short plain-text preview of reader markdown for list rows: syntax is dropped, not rendered,
// and long bodies are cut at a word boundary so the DOM never holds the whole article.
export function markdownPreview(markdown: string): string {
  const text = markdown
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/<[^>]+>/g, " ")
    .replace(/^\s{0,3}(?:#{1,6}|>|[-*+]|\d+[.)])\s+/gm, "")
    .replace(/^\s*(?:[-*_]\s*){3,}$/gm, " ")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\\([\\`*_{}[\]()#+\-.!>~|])/g, "$1")
    .replace(/(\*{1,3}|~~)(\S(?:.*?\S)?)\1/g, "$2")
    // Underscores only mark emphasis at word boundaries, so snake_case words survive.
    .replace(/(^|[^\w])(_{1,3})(\S(?:.*?\S)?)\2(?!\w)/g, "$1$3")
    .replace(/\s+/g, " ")
    .replace(/\s+([,.;:!?])/g, "$1")
    .trim();

  if (text.length <= PREVIEW_MAX_LENGTH) return text;
  const cut = text.slice(0, PREVIEW_MAX_LENGTH);
  const lastSpace = cut.lastIndexOf(" ");
  const trimmed = lastSpace > PREVIEW_MAX_LENGTH * 0.6 ? cut.slice(0, lastSpace) : cut;
  return `${trimmed.replace(/[\s,.;:!?-]+$/, "")}…`;
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
