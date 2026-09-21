import type { APIErrorResponse } from "@/lib/api/generated/model";
import { CompassApiError } from "@/lib/api/client";

function apiPayload(error: unknown): APIErrorResponse | null {
  if (!(error instanceof CompassApiError)) {
    return null;
  }

  const payload = error.data as Partial<APIErrorResponse> | null;
  if (
    !payload ||
    typeof payload !== "object" ||
    !payload.error ||
    typeof payload.error !== "object"
  ) {
    return null;
  }

  return payload as APIErrorResponse;
}

export function getApiErrorCode(error: unknown): string | null {
  return apiPayload(error)?.error.code ?? null;
}

export function getApiErrorMessage(error: unknown): string | null {
  return apiPayload(error)?.error.message ?? null;
}

export function getRetryAfter(error: unknown): number | null {
  if (!(error instanceof CompassApiError)) {
    return null;
  }

  const raw = error.headers["retry-after"];
  if (!raw) {
    return null;
  }

  const seconds = Number.parseInt(raw, 10);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

export function getPasswordPolicyMessages(error: unknown): string[] {
  const details = apiPayload(error)?.error.details;
  if (!Array.isArray(details)) {
    return [];
  }

  return details.flatMap((item) =>
    item &&
    typeof item === "object" &&
    "message" in item &&
    typeof item.message === "string"
      ? [item.message]
      : [],
  );
}

export function friendlyAuthError(
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  const code = getApiErrorCode(error);

  if (code === "rate_limited") {
    const retryAfter = getRetryAfter(error);
    return retryAfter
      ? `Too many attempts. Try again in about ${retryAfter} seconds.`
      : "Too many attempts. Try again in a little while.";
  }

  if (code === "security_unavailable") {
    return "Account security is temporarily unavailable. Please try again later.";
  }

  return getApiErrorMessage(error) ?? fallback;
}
