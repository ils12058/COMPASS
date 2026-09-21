const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);
const API_PREFIX = "/api/v1";

type SerializedHeaders = Record<string, string>;

export class CompassApiError<T = unknown> extends Error {
  readonly status: number;
  readonly data: T;
  readonly headers: SerializedHeaders;
  readonly method: string;
  readonly url: string;

  constructor({
    status,
    data,
    headers,
    method,
    url,
  }: {
    status: number;
    data: T;
    headers: SerializedHeaders;
    method: string;
    url: string;
  }) {
    super(`COMPASS API request failed with status ${status}`);
    this.name = "CompassApiError";
    this.status = status;
    this.data = data;
    this.headers = headers;
    this.method = method;
    this.url = url;
  }
}

export type ErrorType<T> = CompassApiError<T> | TypeError;
export type BodyType<T> = T;

function serializeHeaders(headers: Headers): SerializedHeaders {
  const result: SerializedHeaders = {};

  headers.forEach((value, key) => {
    if (key.toLowerCase() !== "set-cookie") {
      result[key.toLowerCase()] = value;
    }
  });

  return result;
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const prefix = `${encodeURIComponent(name)}=`;

  for (const part of document.cookie.split(";")) {
    const cookie = part.trim();
    if (cookie.startsWith(prefix)) {
      return decodeURIComponent(cookie.slice(prefix.length));
    }
  }

  return null;
}

function normalizeApiUrl(url: string): string {
  if (url === API_PREFIX || url.startsWith(`${API_PREFIX}/`)) {
    return url;
  }

  if (url === "api/v1" || url.startsWith("api/v1/")) {
    return `/${url}`;
  }

  if (/^https?:\/\//i.test(url)) {
    const parsed = new URL(url);
    if (
      parsed.pathname === API_PREFIX ||
      parsed.pathname.startsWith(`${API_PREFIX}/`)
    ) {
      return `${parsed.pathname}${parsed.search}${parsed.hash}`;
    }
  }

  throw new Error(
    `Generated API URL is outside the COMPASS same-origin boundary: ${url}`,
  );
}

async function parseResponseBody(response: Response): Promise<unknown> {
  if ([204, 205, 304].includes(response.status) || !response.body) {
    return undefined;
  }

  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";

  if (contentType.includes("json") || contentType.includes("+json")) {
    const text = await response.text();
    return text ? JSON.parse(text) : undefined;
  }

  if (
    contentType.startsWith("text/") ||
    contentType.includes("xml") ||
    contentType.includes("x-www-form-urlencoded")
  ) {
    return response.text();
  }

  return response.blob();
}

export async function compassFetch<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const requestUrl = normalizeApiUrl(url);
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);

  if (!SAFE_METHODS.has(method) && !headers.has("X-CSRFToken")) {
    const csrfToken = getCookie("csrftoken");
    if (csrfToken) {
      headers.set("X-CSRFToken", csrfToken);
    }
  }

  const response = await fetch(requestUrl, {
    ...options,
    method,
    headers,
    credentials: "include",
  });

  const responseHeaders = serializeHeaders(response.headers);
  const data = await parseResponseBody(response);

  if (!response.ok) {
    throw new CompassApiError({
      status: response.status,
      data,
      headers: responseHeaders,
      method,
      url: requestUrl,
    });
  }

  return {
    data,
    status: response.status,
    headers: responseHeaders,
  } as T;
}
