"use client";

import { useSyncExternalStore, type RefObject } from "react";

function subscribe(listener: () => void) {
  document.addEventListener("fullscreenchange", listener);
  return () => document.removeEventListener("fullscreenchange", listener);
}

const supportedOnClient = () => typeof document !== "undefined" && document.fullscreenEnabled === true && typeof HTMLElement.prototype.requestFullscreen === "function";
const notSupportedOnServer = () => false;

// Full screen for the COMPASS call stage element itself (not a provider frame), where the browser
// allows it. Phones without element full screen simply do not get the control.
export function useFullscreen(target: RefObject<HTMLElement | null>) {
  const supported = useSyncExternalStore(subscribe, supportedOnClient, notSupportedOnServer);
  const active = useSyncExternalStore(
    subscribe,
    () => Boolean(target.current && document.fullscreenElement === target.current),
    notSupportedOnServer,
  );

  async function toggle() {
    const element = target.current;
    if (!supported || !element) return;
    if (document.fullscreenElement === element) await document.exitFullscreen().catch(() => undefined);
    else await element.requestFullscreen().catch(() => undefined);
  }

  return { supported, active, toggle };
}

// Dialogs render in the page body, which a full-screen stage would cover; leave full screen first.
export function leaveFullscreen() {
  if (typeof document !== "undefined" && document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
}
