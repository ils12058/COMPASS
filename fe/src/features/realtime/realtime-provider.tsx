"use client";

import { createContext, useContext, useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";

import { realtimeConfig } from "@/features/realtime/realtime-config";
import type { RealtimeEvent } from "@/features/realtime/realtime-protocol";
import { RealtimeRuntime, type RealtimeSnapshot } from "@/features/realtime/realtime-runtime";
import { requestRealtimeTicket } from "@/features/realtime/realtime-ticket";
import { requestSessionRevalidation } from "@/lib/auth/session-revalidation";

// One realtime runtime per portal tab (ADR-100), mounted by PortalBoundary. Features never open
// sockets: they read the connection state and subscribe to hint types here, and respond by
// re-reading canonical data over HTTP.

const RealtimeContext = createContext<RealtimeRuntime | null>(null);

const DISABLED_SNAPSHOT: RealtimeSnapshot = Object.freeze({ state: "disabled", generation: 0 });
const noSubscription = () => () => {};
const disabledSnapshot = () => DISABLED_SNAPSHOT;

export function createBrowserRealtimeRuntime(): RealtimeRuntime {
  const config = realtimeConfig();
  return new RealtimeRuntime({
    url: config.enabled ? config.url : null,
    requestTicket: requestRealtimeTicket,
    createSocket: (url) => new WebSocket(url),
    onSessionEnded: () => requestSessionRevalidation("session"),
    isOnline: () => typeof navigator === "undefined" || navigator.onLine !== false,
    isVisible: () => typeof document === "undefined" || document.visibilityState !== "hidden",
  });
}

/** `account` is the confirmed user ID, or null while there is none (see `realtimeAccount`). */
export function RealtimeProvider({ account, children }: { account: string | null; children: ReactNode }) {
  const [runtime] = useState(createBrowserRealtimeRuntime);

  useEffect(() => {
    const updateOnline = () => runtime.setOnline(navigator.onLine !== false);
    const updateVisible = () => runtime.setVisible(document.visibilityState !== "hidden");
    updateOnline();
    updateVisible();
    window.addEventListener("online", updateOnline);
    window.addEventListener("offline", updateOnline);
    document.addEventListener("visibilitychange", updateVisible);
    return () => {
      window.removeEventListener("online", updateOnline);
      window.removeEventListener("offline", updateOnline);
      document.removeEventListener("visibilitychange", updateVisible);
    };
  }, [runtime]);

  // Changing accounts runs this cleanup first, so the previous account's socket is closed before
  // the next account's ticket is requested. Unmounting closes it too.
  useEffect(() => {
    runtime.setAccount(account);
    return () => runtime.setAccount(null);
  }, [runtime, account]);

  return <RealtimeContext.Provider value={runtime}>{children}</RealtimeContext.Provider>;
}

/** The portal connection's state and reconciliation generation; `disabled` outside the portal. */
export function useRealtimeStatus(): RealtimeSnapshot {
  const runtime = useContext(RealtimeContext);
  return useSyncExternalStore(
    runtime?.subscribe ?? noSubscription,
    runtime?.getSnapshot ?? disabledSnapshot,
    disabledSnapshot,
  );
}

/** Calls `handler` for each hint of `type` on the shared portal socket. */
export function useRealtimeEvent(type: string, handler: (event: RealtimeEvent) => void): void {
  const runtime = useContext(RealtimeContext);
  const latest = useRef(handler);
  useEffect(() => {
    latest.current = handler;
  });
  useEffect(() => {
    if (!runtime) return;
    return runtime.subscribeEvent(type, (event) => latest.current(event));
  }, [runtime, type]);
}
