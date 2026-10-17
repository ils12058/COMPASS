"use client";

import { useCallback, useSyncExternalStore } from "react";

export const NOTIFICATION_HEADS_UP_PREFERENCE_PREFIX = "compass-notification-heads-up-v1:";

export type NotificationHeadsUpPreference = {
  enabled: boolean;
  ready: boolean;
};

const SERVER_SNAPSHOT: NotificationHeadsUpPreference = Object.freeze({ enabled: true, ready: false });
const snapshots = new Map<string, NotificationHeadsUpPreference>();
const listeners = new Map<string, Set<() => void>>();
let listeningToStorage = false;

export function notificationHeadsUpPreferenceStorageKey(userId: string): string {
  return `${NOTIFICATION_HEADS_UP_PREFERENCE_PREFIX}${encodeURIComponent(userId)}`;
}

export function parseNotificationHeadsUpPreference(raw: string | null): boolean {
  return raw !== "false";
}

function readStoredPreference(userId: string): NotificationHeadsUpPreference {
  try {
    return { enabled: parseNotificationHeadsUpPreference(window.localStorage.getItem(notificationHeadsUpPreferenceStorageKey(userId))), ready: true };
  } catch {
    return { enabled: true, ready: true };
  }
}

function getSnapshot(userId: string): NotificationHeadsUpPreference {
  let snapshot = snapshots.get(userId);
  if (!snapshot) {
    snapshot = readStoredPreference(userId);
    snapshots.set(userId, snapshot);
  }
  return snapshot;
}

function notify(userId: string) {
  listeners.get(userId)?.forEach((listener) => listener());
}

function handleStorage(event: StorageEvent) {
  if (event.key !== null && !event.key.startsWith(NOTIFICATION_HEADS_UP_PREFERENCE_PREFIX)) return;
  for (const userId of listeners.keys()) {
    if (event.key !== null && event.key !== notificationHeadsUpPreferenceStorageKey(userId)) continue;
    snapshots.set(userId, readStoredPreference(userId));
    notify(userId);
  }
}

function subscribe(userId: string, listener: () => void) {
  const accountListeners = listeners.get(userId) ?? new Set<() => void>();
  accountListeners.add(listener);
  listeners.set(userId, accountListeners);
  if (!listeningToStorage) {
    window.addEventListener("storage", handleStorage);
    listeningToStorage = true;
  }

  return () => {
    accountListeners.delete(listener);
    if (accountListeners.size === 0) listeners.delete(userId);
    if (listeners.size === 0 && listeningToStorage) {
      window.removeEventListener("storage", handleStorage);
      listeningToStorage = false;
    }
  };
}

export function setNotificationHeadsUpPreference(userId: string, enabled: boolean) {
  snapshots.set(userId, { enabled, ready: true });
  try {
    const key = notificationHeadsUpPreferenceStorageKey(userId);
    if (enabled) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, "false");
  } catch {
    // The current page still honors the selection when local storage is unavailable.
  }
  notify(userId);
}

export function useNotificationHeadsUpPreference(userId: string): NotificationHeadsUpPreference {
  const subscribeToUser = useCallback((listener: () => void) => subscribe(userId, listener), [userId]);
  const getUserSnapshot = useCallback(() => getSnapshot(userId), [userId]);
  return useSyncExternalStore(subscribeToUser, getUserSnapshot, () => SERVER_SNAPSHOT);
}
