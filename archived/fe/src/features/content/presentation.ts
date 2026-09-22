import { CompassApiError } from "@/lib/api/client";
import { getStructuredApiErrorCode } from "@/lib/api/error-payload";

export const AUDIENCE_OPTIONS = [
  { value: "PUBLIC", label: "Public" },
  { value: "ALL_AUTHENTICATED", label: "Signed-in users" },
  { value: "STUDENTS", label: "Students" },
  { value: "GCO_PERSONNEL", label: "GCO personnel" },
] as const;

export const STATUS_OPTIONS = [
  { value: "DRAFT", label: "Draft" },
  { value: "PUBLISHED", label: "Published" },
  { value: "ARCHIVED", label: "Archived" },
] as const;

export const RESOURCE_CATEGORY_OPTIONS = [
  { value: "GENERAL", label: "General" },
  { value: "COUNSELING", label: "Counseling" },
  { value: "MENTAL_HEALTH", label: "Mental health" },
  { value: "ACADEMIC_SUPPORT", label: "Academic support" },
  { value: "CAREER", label: "Career" },
  { value: "WELLNESS", label: "Wellness" },
  { value: "FORMS_AND_GUIDES", label: "Forms and guides" },
  { value: "OTHER", label: "Other" },
] as const;

export const RESOURCE_KIND_OPTIONS = [
  {
    value: "ARTICLE",
    label: "Article",
    description: "Information that readers can read directly in COMPASS.",
  },
  {
    value: "EXTERNAL_LINK",
    label: "External link",
    description: "A trusted webpage readers can open from COMPASS.",
  },
  {
    value: "FILE",
    label: "PDF file",
    description: "A PDF document readers can download through COMPASS.",
  },
] as const;

export const PDF_MAX_BYTES = 10 * 1024 * 1024;

export function audienceLabel(value: string): string {
  return AUDIENCE_OPTIONS.find((option) => option.value === value)?.label ?? value;
}

export function statusLabel(value: string): string {
  return STATUS_OPTIONS.find((option) => option.value === value)?.label ?? value;
}

export function resourceCategoryLabel(value: string): string {
  return (
    RESOURCE_CATEGORY_OPTIONS.find((option) => option.value === value)?.label ??
    value
  );
}

export function resourceKindLabel(value: string): string {
  return RESOURCE_KIND_OPTIONS.find((option) => option.value === value)?.label ?? value;
}

export function formatContentDateTime(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

export function toDateTimeLocal(value: string | null | undefined): string {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return [
    date.getFullYear(),
    "-",
    pad(date.getMonth() + 1),
    "-",
    pad(date.getDate()),
    "T",
    pad(date.getHours()),
    ":",
    pad(date.getMinutes()),
  ].join("");
}

export function fromDateTimeLocal(value: string): string | null {
  if (!value) {
    return null;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function isExpired(expiresAt: string | null | undefined): boolean {
  if (!expiresAt) {
    return false;
  }

  const expires = Date.parse(expiresAt);
  return Number.isFinite(expires) && expires <= Date.now();
}

export function isSafeExternalHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return (
      (url.protocol === "http:" || url.protocol === "https:") &&
      Boolean(url.hostname) &&
      !url.username &&
      !url.password
    );
  } catch {
    return false;
  }
}

export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "—";
  }
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function backendMessage(error: CompassApiError): string | null {
  const data = error.data;
  if (!data || typeof data !== "object" || !("error" in data)) {
    return null;
  }

  const detail = (data as { error?: unknown }).error;
  if (!detail || typeof detail !== "object" || !("message" in detail)) {
    return null;
  }

  const message = (detail as { message?: unknown }).message;
  return typeof message === "string" && message.trim() ? message : null;
}

export function contentMutationError(
  error: unknown,
  domain: "announcement" | "resource",
): string | null {
  if (!(error instanceof CompassApiError)) {
    return "The action could not be completed. Please try again.";
  }

  const code = getStructuredApiErrorCode(error.data);
  if (code === "maintenance_mode") {
    return null;
  }
  if (code === "permission_denied") {
    return "This action is not available to your account.";
  }
  if (code === "announcement_not_found" || code === "resource_not_found") {
    return "This item could not be found.";
  }
  if (code === "announcement_not_editable") {
    return "This announcement can no longer be changed.";
  }
  if (code === "resource_conflict") {
    return "The resource changed or this action is no longer available.";
  }
  if (code === "resource_storage_unavailable") {
    return "PDF storage is temporarily unavailable. Try again later.";
  }
  if (code === "invalid_announcement_input" || code === "invalid_resource_input") {
    return backendMessage(error) ?? "Please review the information and try again.";
  }

  return `The ${domain} action could not be completed. Please try again.`;
}
