// The realtime wire protocol (ADR-100), mirrored from the backend's realtime_service.protocol.
// Server frames are content-free hints: a version, a type, and at most opaque identifiers.

export const REALTIME_CLOSE = {
  policyViolation: 1008,
  tryAgainLater: 1013,
  /** The bounded connection lifetime ended: reconnect promptly with a fresh ticket. */
  reconnect: 4000,
  authenticationFailed: 4401,
  /** The AuthSession was revoked: the HTTP session must be checked again. */
  sessionRevoked: 4403,
  authenticationTimeout: 4408,
} as const;

export type RealtimeEvent = Readonly<{ v: 1; type: string } & Record<string, string | number>>;

export type ServerFrame = { kind: "ready" } | { kind: "event"; event: RealtimeEvent };

const MAX_FRAME_CHARS = 512;
const EVENT_TYPE = /^[a-z][a-z_]*(?:\.[a-z][a-z_]*)+$/;
const FIELD_NAME = /^[a-z][a-z_]*$/;
const OPAQUE_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/** The one frame a client sends: protocol authentication, not a command. */
export function authenticateFrame(ticket: string): string {
  return JSON.stringify({ type: "authenticate", ticket });
}

export function parseServerFrame(data: unknown): ServerFrame | null {
  if (typeof data !== "string" || data.length > MAX_FRAME_CHARS) return null;
  let value: unknown;
  try {
    value = JSON.parse(data);
  } catch {
    return null;
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const frame = value as Record<string, unknown>;
  if (frame.v !== 1 || typeof frame.type !== "string") return null;
  const fields = Object.entries(frame).filter(([name]) => name !== "v" && name !== "type");
  if (frame.type === "ready") return fields.length === 0 ? { kind: "ready" } : null;
  if (!EVENT_TYPE.test(frame.type)) return null;
  if (!fields.every(([name, field]) => FIELD_NAME.test(name) && typeof field === "string" && OPAQUE_ID.test(field))) {
    return null;
  }
  return { kind: "event", event: frame as RealtimeEvent };
}
