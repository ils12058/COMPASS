import type { PlatformPublicStatusResponse } from "@/lib/api/generated/model";

const PUBLIC_STATUS_KEYS = ["ends_at", "message", "starts_at", "status"] as const;
const BACKEND_STATUSES = new Set([
  "operational",
  "maintenance_scheduled",
  "maintenance_active",
]);

export type ServiceStatusView =
  | Readonly<{ kind: "unknown" }>
  | Readonly<{ kind: "operational" }>
  | Readonly<{ kind: "offline" }>
  | Readonly<{ kind: "unavailable" }>
  | Readonly<{
      kind: "maintenance_scheduled";
      message: string;
      startsAt: string;
      endsAt: string;
    }>
  | Readonly<{
      kind: "maintenance_active";
      message: string;
      startsAt: string | null;
      endsAt: string | null;
    }>;

export const UNKNOWN_SERVICE_STATUS: ServiceStatusView = { kind: "unknown" };

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isDateString(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}

export function parsePlatformPublicStatus(
  value: unknown,
): PlatformPublicStatusResponse | null {
  if (!isRecord(value)) {
    return null;
  }

  const keys = Object.keys(value).sort();
  if (
    keys.length !== PUBLIC_STATUS_KEYS.length ||
    keys.some((key, index) => key !== PUBLIC_STATUS_KEYS[index])
  ) {
    return null;
  }

  if (typeof value.status !== "string" || !BACKEND_STATUSES.has(value.status)) {
    return null;
  }

  if (value.message !== null && typeof value.message !== "string") {
    return null;
  }

  if (value.starts_at !== null && !isDateString(value.starts_at)) {
    return null;
  }

  if (value.ends_at !== null && !isDateString(value.ends_at)) {
    return null;
  }

  return value as unknown as PlatformPublicStatusResponse;
}

function validWindow(startsAt: string, endsAt: string): boolean {
  return Date.parse(endsAt) > Date.parse(startsAt);
}

export function normalizeServiceStatus(
  status: PlatformPublicStatusResponse,
): ServiceStatusView {
  if (status.status === "operational") {
    return status.message === null &&
      status.starts_at === null &&
      status.ends_at === null
      ? { kind: "operational" }
      : { kind: "unavailable" };
  }

  if (
    status.status === "maintenance_scheduled" &&
    typeof status.message === "string" &&
    status.message.length > 0 &&
    status.starts_at !== null &&
    status.ends_at !== null &&
    validWindow(status.starts_at, status.ends_at)
  ) {
    return {
      kind: "maintenance_scheduled",
      message: status.message,
      startsAt: status.starts_at,
      endsAt: status.ends_at,
    };
  }

  if (
    status.status === "maintenance_active" &&
    typeof status.message === "string" &&
    status.message.length > 0
  ) {
    if (status.starts_at === null) {
      return {
        kind: "maintenance_active",
        message: status.message,
        startsAt: null,
        endsAt: status.ends_at,
      };
    }

    if (
      status.ends_at !== null &&
      validWindow(status.starts_at, status.ends_at)
    ) {
      return {
        kind: "maintenance_active",
        message: status.message,
        startsAt: status.starts_at,
        endsAt: status.ends_at,
      };
    }
  }

  return { kind: "unavailable" };
}
