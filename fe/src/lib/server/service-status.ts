import "server-only";

import type { PlatformPublicStatusResponse } from "@/lib/api/generated/model";
import { parsePlatformPublicStatus } from "@/lib/system/service-status";

const STATUS_PATH = "/api/v1/platform/status";
const STATUS_TIMEOUT_MS = 1_500;

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
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
      signal: AbortSignal.timeout(STATUS_TIMEOUT_MS),
    });

    if (!response.ok) {
      return null;
    }

    return parsePlatformPublicStatus(await response.json());
  } catch {
    return null;
  }
}
