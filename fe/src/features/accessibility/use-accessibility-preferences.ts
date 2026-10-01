"use client";

import { useSyncExternalStore } from "react";

import {
  ACCESSIBILITY_STORAGE_KEY,
  DEFAULT_ACCESSIBILITY_PREFERENCES,
  accessibilityAttributes,
  isDefaultAccessibility,
  parseAccessibilityPreferences,
  type AccessibilityPreferences,
} from "@/features/accessibility/accessibility-preferences";

let snapshot: AccessibilityPreferences | null = null;
const listeners = new Set<() => void>();

function readStoredPreferences(): AccessibilityPreferences {
  try {
    return parseAccessibilityPreferences(window.localStorage.getItem(ACCESSIBILITY_STORAGE_KEY));
  } catch {
    return { ...DEFAULT_ACCESSIBILITY_PREFERENCES };
  }
}

function applyToDocument(preferences: AccessibilityPreferences) {
  const root = document.documentElement;
  for (const [name, value] of Object.entries(accessibilityAttributes(preferences))) {
    if (value === null) root.removeAttribute(name);
    else root.setAttribute(name, value);
  }
}

function notify() {
  for (const listener of listeners) listener();
}

// Another tab changed (or cleared) the saved preferences.
function handleStorage(event: StorageEvent) {
  if (event.key !== null && event.key !== ACCESSIBILITY_STORAGE_KEY) return;
  snapshot = readStoredPreferences();
  applyToDocument(snapshot);
  notify();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (listeners.size === 1) window.addEventListener("storage", handleStorage);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) window.removeEventListener("storage", handleStorage);
  };
}

function getSnapshot(): AccessibilityPreferences {
  snapshot ??= readStoredPreferences();
  return snapshot;
}

function getServerSnapshot(): AccessibilityPreferences {
  return DEFAULT_ACCESSIBILITY_PREFERENCES;
}

export function updateAccessibilityPreferences(next: AccessibilityPreferences) {
  snapshot = next;
  try {
    if (isDefaultAccessibility(next)) window.localStorage.removeItem(ACCESSIBILITY_STORAGE_KEY);
    else window.localStorage.setItem(ACCESSIBILITY_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Storage can be blocked (for example in private browsing); the change still applies here.
  }
  applyToDocument(next);
  notify();
}

export function useAccessibilityPreferences(): AccessibilityPreferences {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeToReducedMotion(onChange: () => void) {
  const query = window.matchMedia(REDUCED_MOTION_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

// JavaScript-driven motion must use this rather than the media query alone: it also honors the
// reader's COMPASS "Reduce motion" setting.
export function useReducedMotion(): boolean {
  const systemReduced = useSyncExternalStore(
    subscribeToReducedMotion,
    () => window.matchMedia(REDUCED_MOTION_QUERY).matches,
    () => false,
  );
  const { reduceMotion } = useAccessibilityPreferences();
  return systemReduced || reduceMotion;
}
