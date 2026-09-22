import type { PlatformPublicStatusResponse } from "@/lib/api/generated/model";

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

function isDateString(value: string): boolean {
  return Number.isFinite(Date.parse(value));
}

function validWindow(startsAt: string, endsAt: string): boolean {
  return isDateString(startsAt) && isDateString(endsAt) && Date.parse(endsAt) > Date.parse(startsAt);
}

export function normalizeServiceStatus(
  status: PlatformPublicStatusResponse,
): ServiceStatusView {
  const message = typeof status.message === "string" ? status.message.trim() : "";

  if (
    status.status === "operational" &&
    message.length === 0 &&
    status.starts_at === null &&
    status.ends_at === null
  ) {
    return { kind: "operational" };
  }

  if (
    status.status === "maintenance_scheduled" &&
    message.length > 0 &&
    status.starts_at !== null &&
    status.ends_at !== null &&
    validWindow(status.starts_at, status.ends_at)
  ) {
    return {
      kind: "maintenance_scheduled",
      message,
      startsAt: status.starts_at,
      endsAt: status.ends_at,
    };
  }

  if (status.status === "maintenance_active" && message.length > 0) {
    if (status.starts_at === null) {
      return {
        kind: "maintenance_active",
        message,
        startsAt: null,
        endsAt: status.ends_at !== null && isDateString(status.ends_at) ? status.ends_at : null,
      };
    }

    if (
      isDateString(status.starts_at) &&
      (status.ends_at === null || validWindow(status.starts_at, status.ends_at))
    ) {
      return {
        kind: "maintenance_active",
        message,
        startsAt: status.starts_at,
        endsAt: status.ends_at,
      };
    }
  }

  return { kind: "unavailable" };
}
