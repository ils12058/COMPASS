type ResponseHeaders = Record<string, string>;

export class CompassApiError extends Error {
  readonly status: number;
  readonly body: unknown;
  readonly headers: ResponseHeaders;
  readonly method: string;
  readonly url: string;

  constructor({
    status,
    body,
    headers,
    method,
    url,
  }: {
    status: number;
    body: unknown;
    headers: ResponseHeaders;
    method: string;
    url: string;
  }) {
    super(readApiErrorMessage(body) ?? `Request failed with status ${status}.`);
    this.name = "CompassApiError";
    this.status = status;
    this.body = body;
    this.headers = headers;
    this.method = method;
    this.url = url;
  }
}

export function readApiErrorCode(body: unknown): string | undefined {
  const error = getErrorObject(body);
  return typeof error?.code === "string" ? error.code : undefined;
}

export function readApiErrorMessage(body: unknown): string | undefined {
  const error = getErrorObject(body);
  return typeof error?.message === "string" ? error.message : undefined;
}

function getErrorObject(body: unknown): Record<string, unknown> | undefined {
  if (!body || typeof body !== "object" || !("error" in body)) {
    return undefined;
  }

  const error = body.error;
  return error && typeof error === "object"
    ? (error as Record<string, unknown>)
    : undefined;
}
