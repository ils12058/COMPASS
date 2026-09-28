import { clearCsrfToken, getCsrfToken } from "@/lib/api/csrf";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { parseResponseBody } from "@/lib/api/response-body";

const API_ROOT = "/api/v1";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

export type ErrorType<T = unknown> = CompassApiError & { body: T };
export type BodyType<T> = T;

function normalizeApiUrl(url: string): string {
  const normalized = url.startsWith("api/v1") ? `/${url}` : url;

  if (
    normalized === API_ROOT ||
    normalized.startsWith(`${API_ROOT}/`) ||
    normalized.startsWith(`${API_ROOT}?`)
  ) {
    return normalized;
  }

  throw new Error(`API request is outside the COMPASS boundary: ${url}`);
}

function serializeHeaders(headers: Headers): Record<string, string> {
  const values: Record<string, string> = {};
  headers.forEach((value, key) => {
    if (key.toLowerCase() !== "set-cookie") {
      values[key.toLowerCase()] = value;
    }
  });
  return values;
}

export async function compassFetch<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const requestUrl = normalizeApiUrl(url);
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);

  if (!SAFE_METHODS.has(method) && !headers.has("X-CSRFToken")) {
    headers.set("X-CSRFToken", await getCsrfToken());
  }

  const response = await fetch(requestUrl, {
    ...options,
    method,
    headers,
    credentials: "include",
  });
  const body = await parseResponseBody(response);
  const responseHeaders = serializeHeaders(response.headers);

  if (!response.ok) {
    if (response.status === 403 && readApiErrorCode(body) === "csrf_failed") {
      clearCsrfToken();
    }

    throw new CompassApiError({
      status: response.status,
      body,
      headers: responseHeaders,
      method,
      url: requestUrl,
    });
  }

  return {
    data: body,
    status: response.status,
    headers: responseHeaders,
  } as T;
}
