"use client";

import { useEffect, useState } from "react";

import { useRealtimeEvent } from "@/features/realtime/realtime-provider";
import type { RealtimeEvent } from "@/features/realtime/realtime-protocol";
import { guidanceMessagesSignalTyping } from "@/lib/api/generated/guidance-messages/guidance-messages";

// Typing indicators (GMSG-7). The writer's portal tells the backend "I am writing here" at most
// every few seconds while the draft keeps changing; the backend sends the other side a content-free
// `messages.typing_changed {thread_id}` hint. Nothing about the draft ever leaves the browser, and
// the receiver expires the indicator itself, so a lost "stopped" can never leave it stuck.
// Timings are provisional engineering defaults (D-GMSG-13), not GCO-approved values.

/** The writer sends at most one signal per thread in this interval (the backend allows one per 3 s). */
export const TYPING_SIGNAL_INTERVAL_MS = 3_500;
/** The receiver hides the indicator this long after the last hint. */
export const TYPING_INDICATOR_TTL_MS = 8_000;

/** The thread a `messages.typing_changed` hint names, or null for any other or malformed hint. */
export function typingThreadId(event: RealtimeEvent): string | null {
  return event.type === "messages.typing_changed" && typeof event.thread_id === "string" ? event.thread_id : null;
}

/**
 * The writer's throttle, separate from React so it can be tested. `update` is called with each
 * draft; it signals only when the draft changed, is not blank, and the interval has passed for that
 * conversation. A cleared draft or another conversation resets the throttle, so the next burst of
 * writing is announced promptly.
 */
export function createTypingSignal(signal: (threadId: string) => void, now: () => number = Date.now) {
  let lastThread: string | null = null;
  let lastDraft = "";
  let lastSignal = Number.NEGATIVE_INFINITY;
  return {
    update(draft: string, threadId: string) {
      if (threadId !== lastThread) {
        lastThread = threadId;
        lastDraft = "";
        lastSignal = Number.NEGATIVE_INFINITY;
      }
      const changed = draft !== lastDraft;
      lastDraft = draft;
      if (!draft.trim()) {
        lastSignal = Number.NEGATIVE_INFINITY;
        return false;
      }
      if (!changed || now() - lastSignal < TYPING_SIGNAL_INTERVAL_MS) return false;
      lastSignal = now();
      signal(threadId);
      return true;
    },
  };
}

function sendTypingSignal(threadId: string) {
  // Advisory only: a refused or failed signal changes nothing the reader can see.
  void guidanceMessagesSignalTyping(threadId).catch(() => undefined);
}

/** Signals while the reader writes in an existing, open conversation. Failures are silent. */
export function useTypingSignal(threadId: string | null | undefined, draft: string, enabled: boolean) {
  const [throttle] = useState(() => createTypingSignal(sendTypingSignal));
  useEffect(() => {
    if (!enabled || !threadId) return;
    throttle.update(draft, threadId);
  }, [draft, enabled, threadId, throttle]);
}

/**
 * Whether the other side is writing in `threadId` now. A hint shows it for a few seconds and each
 * further hint extends that; a newer Message from the other side (`resetKey`) or a closed
 * conversation hides it at once.
 */
export function useCounterpartTyping(threadId: string, enabled: boolean, resetKey: number): boolean {
  const key = `${threadId}:${resetKey}`;
  const [shown, setShown] = useState<{ key: string; hint: number } | null>(null);

  useRealtimeEvent("messages.typing_changed", (event) => {
    if (!enabled || typingThreadId(event) !== threadId) return;
    setShown((previous) => ({ key, hint: (previous?.hint ?? 0) + 1 }));
  });

  useEffect(() => {
    if (!shown) return;
    const timer = setTimeout(() => setShown(null), TYPING_INDICATOR_TTL_MS);
    return () => clearTimeout(timer);
  }, [shown]);

  return enabled && shown !== null && shown.key === key;
}
