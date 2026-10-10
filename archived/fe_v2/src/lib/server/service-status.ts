import "server-only";

import type { PlatformPublicStatusResponse } from "@/lib/api/generated/model";

const STATUS_PATH = "/api/v1/platform/status";
const STATUS_TIMEOUT_MS = 1_500;

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export async function getInitialPlatformStatus(): Promise<PlatformPublicStatusResponse | null> {
  const baseUrl = process.env.COMPASS_API_BASE_URL?.trim();
  if (!baseUrl) {
    return null;
  }

  let url: string;
  try {
    const parsed = new URL(baseUrl);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }
    url = `${baseUrl.replace(/\/+$/, "")}${STATUS_PATH}`;
  } catch {
    return null;
  }

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
      credentials: "omit",
      signal: AbortSignal.timeout(STATUS_TIMEOUT_MS),
    });

    if (!response.ok) {
      return null;
    }

    const body: unknown = await response.json();
    return isObject(body)
      ? (body as unknown as PlatformPublicStatusResponse)
      : null;
  } catch {
    return null;
  }
}
