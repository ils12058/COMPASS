"use client";

import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import {
  guidanceConversationQueryKey,
  guidanceDirectoryQueryFamily,
  guidanceThreadQueryKey,
} from "@/features/guidance-messages/guidance-messages-cache";
import { useRealtimeEvent, useRealtimeStatus } from "@/features/realtime/realtime-provider";
import type { RealtimeEvent } from "@/features/realtime/realtime-protocol";
import type { RealtimeSnapshot } from "@/features/realtime/realtime-runtime";

// Messages freshness while the workspace is open. Realtime hints only say that a thread changed;
// HTTP stays authoritative, and polling heals hints lost while disconnected (ADR-100, ADR-102):
// about every 8 seconds when the socket is not live, every 60 seconds as a safety net when it is,
// and promptly when the tab becomes visible, regains focus, comes back online, or the socket is
// ready again. Hidden or offline tabs do not poll.
export const MESSAGES_FALLBACK_REFRESH_MS = 8_000;
export const MESSAGES_LIVE_SAFETY_REFRESH_MS = 60_000;

/** What one reconciliation covers: the directory always, the open thread when it may have changed. */
export type MessagesRefreshScope = { activeThread: boolean };

type FreshnessEnvironment = {
  document: Pick<Document, "visibilityState" | "addEventListener" | "removeEventListener">;
  window: Pick<Window, "setInterval" | "clearInterval" | "addEventListener" | "removeEventListener">;
  navigator: Pick<Navigator, "onLine">;
};

export function startGuidanceMessagesFreshness(
  reconcile: (scope: MessagesRefreshScope) => Promise<unknown>,
  environment: FreshnessEnvironment,
  // The socket generation the workspace opened under. Its queries are loading already; only a
  // later `ready` means hints may have been missed.
  initialGeneration = 0,
) {
  let refreshing = false;
  // Requests that arrive during a reconciliation collapse into one trailing reconciliation that
  // covers everything they asked for. Kept while hidden or offline until a refresh can run.
  let requested: MessagesRefreshScope | null = null;
  let stopped = false;
  let generation = initialGeneration;
  let interval = MESSAGES_FALLBACK_REFRESH_MS;

  function canRefresh() {
    return !stopped && environment.document.visibilityState === "visible" && environment.navigator.onLine;
  }

  async function run() {
    if (!canRefresh() || refreshing || requested === null) return;
    const scope = requested;
    requested = null;
    refreshing = true;
    try {
      await reconcile(scope);
    } catch {
      // A failed read keeps its own error state; the next signal tries again.
    } finally {
      refreshing = false;
      if (requested !== null && canRefresh()) void run();
    }
  }

  function requestRefresh(scope: MessagesRefreshScope = { activeThread: true }) {
    if (stopped) return;
    requested = { activeThread: (requested?.activeThread ?? false) || scope.activeThread };
    void run();
  }

  const everything = () => requestRefresh({ activeThread: true });
  let timer = environment.window.setInterval(everything, interval);

  function setRealtimeStatus(snapshot: RealtimeSnapshot) {
    if (stopped) return;
    const nextInterval = snapshot.state === "live" ? MESSAGES_LIVE_SAFETY_REFRESH_MS : MESSAGES_FALLBACK_REFRESH_MS;
    if (nextInterval !== interval) {
      environment.window.clearInterval(timer);
      interval = nextInterval;
      timer = environment.window.setInterval(everything, interval);
    }
    // A fresh `ready`: hints sent while disconnected were lost, so reconcile the whole workspace.
    if (snapshot.generation > generation) {
      generation = snapshot.generation;
      everything();
    }
  }

  const onVisible = () => {
    if (environment.document.visibilityState === "visible") everything();
  };
  environment.document.addEventListener("visibilitychange", onVisible);
  environment.window.addEventListener("focus", onVisible);
  environment.window.addEventListener("online", everything);

  function stop() {
    stopped = true;
    requested = null;
    environment.window.clearInterval(timer);
    environment.document.removeEventListener("visibilitychange", onVisible);
    environment.window.removeEventListener("focus", onVisible);
    environment.window.removeEventListener("online", everything);
  }

  return { requestRefresh, setRealtimeStatus, stop };
}

/** Re-reads the directory and, when asked, the open thread's detail and newest history page. */
export function reconcileGuidanceMessages(
  queryClient: Pick<QueryClient, "invalidateQueries">,
  activeThreadId: string | null,
  scope: MessagesRefreshScope,
) {
  const reads = [queryClient.invalidateQueries({ queryKey: guidanceDirectoryQueryFamily() })];
  if (scope.activeThread && activeThreadId) {
    reads.push(
      queryClient.invalidateQueries({ queryKey: guidanceThreadQueryKey(activeThreadId), exact: true }),
      queryClient.invalidateQueries({ queryKey: guidanceConversationQueryKey(activeThreadId), exact: true }),
    );
  }
  return Promise.allSettled(reads);
}

/** The thread a `messages.thread_changed` hint names, or null for any other or malformed hint. */
export function changedThreadId(event: RealtimeEvent): string | null {
  return event.type === "messages.thread_changed" && typeof event.thread_id === "string" ? event.thread_id : null;
}

/**
 * Runs one freshness scheduler while the calling surface is mounted. `reconcile` re-reads what the
 * surface shows; `hintScope` turns a `messages.thread_changed` hint into a refresh request, or null
 * when the hint does not concern the surface. The full workspace and a contextual panel never mount
 * together, so a page has at most one scheduler.
 */
export function useMessagesFreshness({
  reconcile,
  hintScope,
}: {
  reconcile: (scope: MessagesRefreshScope) => Promise<unknown>;
  hintScope: (threadId: string) => MessagesRefreshScope | null;
}) {
  const { state, generation } = useRealtimeStatus();
  const latest = useRef({ reconcile, hintScope });
  const openedAt = useRef(generation);
  const freshness = useRef<ReturnType<typeof startGuidanceMessagesFreshness> | null>(null);

  useEffect(() => {
    latest.current = { reconcile, hintScope };
  });

  useEffect(() => {
    const consumer = startGuidanceMessagesFreshness(
      (scope) => latest.current.reconcile(scope),
      { document, window, navigator },
      openedAt.current,
    );
    freshness.current = consumer;
    return () => {
      consumer.stop();
      freshness.current = null;
    };
  }, []);

  useEffect(() => {
    freshness.current?.setRealtimeStatus({ state, generation });
  }, [state, generation]);

  useRealtimeEvent("messages.thread_changed", (event) => {
    const threadId = changedThreadId(event);
    if (!threadId) return;
    const scope = latest.current.hintScope(threadId);
    if (scope) freshness.current?.requestRefresh(scope);
  });
}

/** The full workspace: the directory always, the open thread when a hint names it. */
export function useGuidanceMessagesFreshness(activeThreadId: string | null) {
  const queryClient = useQueryClient();
  const active = useRef(activeThreadId);

  useEffect(() => {
    active.current = activeThreadId;
  }, [activeThreadId]);

  useMessagesFreshness({
    reconcile: (scope) => reconcileGuidanceMessages(queryClient, active.current, scope),
    // Ordering, unread counts, status and assignment can change for any thread, so the directory
    // is always reconciled. The open thread is re-read only when the hint names it.
    hintScope: (threadId) => ({ activeThread: threadId === active.current }),
  });
}
