import { CompassApiError } from "@/lib/api/errors";

// One intended Message has one client_message_id (ADR-102). The backend returns the original
// Message when the same sender sends the same ID to the same thread again, so a retry after an
// unconfirmed outcome is safe only with the same ID and the same body. A new intended Message, or
// the same draft after it was deliberately edited, gets a new ID.

/** Matches the backend's 4,000 Unicode characters (code points, not UTF-16 units). */
export const MESSAGE_BODY_LIMIT = 4000;

export type MessageBodyProblem = "empty" | "too_long" | "unsupported";

export function messageLength(body: string): number {
  return [...body].length;
}

// A lone surrogate cannot be encoded as UTF-8, so the backend would refuse it.
function hasLoneSurrogate(body: string): boolean {
  for (let index = 0; index < body.length; index += 1) {
    const unit = body.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = body.charCodeAt(index + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) return true;
      index += 1;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      return true;
    }
  }
  return false;
}

export function messageBodyProblem(body: string): MessageBodyProblem | null {
  if (!body.trim()) return "empty";
  if (messageLength(body) > MESSAGE_BODY_LIMIT) return "too_long";
  if (body.includes("\u0000") || hasLoneSurrogate(body)) return "unsupported";
  return null;
}

export const MESSAGE_BODY_PROBLEMS: Record<MessageBodyProblem, string> = {
  empty: "Write a message before sending.",
  too_long: `Messages can be up to ${MESSAGE_BODY_LIMIT.toLocaleString("en-PH")} characters. Shorten this message to send it.`,
  unsupported: "This message contains a character COMPASS cannot send. Remove it and try again.",
};

/** Where one intended Message goes: an open thread, the Guidance Office, or a relationship. */
export type SendTarget = string;

export type SendIntent = Readonly<{ target: SendTarget; clientMessageId: string; body: string }>;

export type SendState =
  | { kind: "idle" }
  | { kind: "sending"; intent: SendIntent }
  // The request may have reached COMPASS. Only a retry of exactly this intent is allowed until the
  // reader deliberately sets it aside.
  | { kind: "uncertain"; intent: SendIntent };

export const IDLE_SEND: SendState = { kind: "idle" };

/**
 * The intent to submit, or null when a submission must not start: one is already in flight, or an
 * unconfirmed one is waiting for its retry and the reader changed the target or text.
 */
export function nextSendIntent(
  state: SendState,
  target: SendTarget,
  body: string,
  createId: () => string,
): SendIntent | null {
  if (state.kind === "sending") return null;
  if (state.kind === "uncertain") {
    const { intent } = state;
    return intent.target === target && intent.body === body ? intent : null;
  }
  return { target, clientMessageId: createId(), body };
}

/**
 * Whether a failed send may still have been stored. A network failure, a timeout or a server error
 * can follow a committed Message, so the same intent must be kept for its retry. Any other refusal
 * (validation, conflict, session or access) means nothing was stored.
 */
export function isUncertainSendFailure(error: unknown): boolean {
  if (!(error instanceof CompassApiError)) return true;
  return error.status >= 500 || error.status === 408;
}

export function createClientMessageId(): string | null {
  return typeof globalThis.crypto?.randomUUID === "function" ? globalThis.crypto.randomUUID() : null;
}
