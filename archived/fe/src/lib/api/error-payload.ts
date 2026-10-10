const CANONICAL_UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type StructuredErrorEnvelope = {
  error?: {
    code?: unknown;
    request_id?: unknown;
  };
};

function envelope(value: unknown): StructuredErrorEnvelope | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as StructuredErrorEnvelope)
    : null;
}

export function getStructuredApiErrorCode(value: unknown): string | null {
  const code = envelope(value)?.error?.code;
  return typeof code === "string" ? code : null;
}

export function getStructuredApiRequestId(value: unknown): string | null {
  const requestId = envelope(value)?.error?.request_id;
  if (typeof requestId !== "string" || !CANONICAL_UUID.test(requestId)) {
    return null;
  }
  return requestId;
}
