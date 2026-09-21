"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useSyncExternalStore,
} from "react";

const STORAGE_KEY = "compass-accessibility-preferences-v1";
const CHANGE_EVENT = "compass:accessibility-preferences-change";
const MAX_STORED_LENGTH = 512;

export type AccessibilityTextSize = "default" | "large" | "extra-large";
export type AccessibilityContrast = "default" | "high";
export type AccessibilitySpacing = "default" | "relaxed";
export type AccessibilityMotion = "system" | "reduced";

export type AccessibilityPreferences = Readonly<{
  textSize: AccessibilityTextSize;
  contrast: AccessibilityContrast;
  spacing: AccessibilitySpacing;
  underlineLinks: boolean;
  motion: AccessibilityMotion;
}>;

type AccessibilityPreferencesContextValue = {
  preferences: AccessibilityPreferences;
  setTextSize: (value: AccessibilityTextSize) => void;
  setContrast: (value: AccessibilityContrast) => void;
  setSpacing: (value: AccessibilitySpacing) => void;
  setUnderlineLinks: (value: boolean) => void;
  setMotion: (value: AccessibilityMotion) => void;
  restoreDefaults: () => void;
};

const DEFAULT_PREFERENCES: AccessibilityPreferences = Object.freeze({
  textSize: "default",
  contrast: "default",
  spacing: "default",
  underlineLinks: false,
  motion: "system",
});

const EXPECTED_KEYS = [
  "contrast",
  "motion",
  "spacing",
  "textSize",
  "underlineLinks",
] as const;

let memoryPreferences = DEFAULT_PREFERENCES;
let cachedRaw: string | null | undefined;
let cachedPreferences = DEFAULT_PREFERENCES;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isOneOf<T extends string>(
  value: unknown,
  values: readonly T[],
): value is T {
  return typeof value === "string" && values.includes(value as T);
}

function parseStoredPreferences(raw: string | null): AccessibilityPreferences {
  if (!raw || raw.length > MAX_STORED_LENGTH) {
    return DEFAULT_PREFERENCES;
  }

  try {
    const value: unknown = JSON.parse(raw);
    if (!isRecord(value)) {
      return DEFAULT_PREFERENCES;
    }

    const keys = Object.keys(value).sort();
    if (
      keys.length !== EXPECTED_KEYS.length ||
      keys.some((key, index) => key !== EXPECTED_KEYS[index])
    ) {
      return DEFAULT_PREFERENCES;
    }

    if (
      !isOneOf(value.textSize, ["default", "large", "extra-large"] as const) ||
      !isOneOf(value.contrast, ["default", "high"] as const) ||
      !isOneOf(value.spacing, ["default", "relaxed"] as const) ||
      typeof value.underlineLinks !== "boolean" ||
      !isOneOf(value.motion, ["system", "reduced"] as const)
    ) {
      return DEFAULT_PREFERENCES;
    }

    return Object.freeze({
      textSize: value.textSize,
      contrast: value.contrast,
      spacing: value.spacing,
      underlineLinks: value.underlineLinks,
      motion: value.motion,
    });
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function getClientSnapshot(): AccessibilityPreferences {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === cachedRaw) {
      return cachedPreferences;
    }

    cachedRaw = raw;
    cachedPreferences = parseStoredPreferences(raw);
    memoryPreferences = cachedPreferences;
    return cachedPreferences;
  } catch {
    return memoryPreferences;
  }
}

function getServerSnapshot(): AccessibilityPreferences {
  return DEFAULT_PREFERENCES;
}

function subscribe(onStoreChange: () => void): () => void {
  const handleStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) {
      cachedRaw = undefined;
      onStoreChange();
    }
  };
  const handleLocalChange = () => {
    cachedRaw = undefined;
    onStoreChange();
  };

  window.addEventListener("storage", handleStorage);
  window.addEventListener(CHANGE_EVENT, handleLocalChange);

  return () => {
    window.removeEventListener("storage", handleStorage);
    window.removeEventListener(CHANGE_EVENT, handleLocalChange);
  };
}

function publishPreferences(preferences: AccessibilityPreferences): void {
  memoryPreferences = preferences;
  cachedRaw = undefined;

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    // Keep the preference available in memory when browser storage is unavailable.
  }

  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function removeStoredPreferences(): void {
  memoryPreferences = DEFAULT_PREFERENCES;
  cachedRaw = undefined;

  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Defaults still apply in memory when browser storage is unavailable.
  }

  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function applyPreferences(preferences: AccessibilityPreferences): void {
  const root = document.documentElement;
  root.dataset.compassTextSize = preferences.textSize;
  root.dataset.compassContrast = preferences.contrast;
  root.dataset.compassSpacing = preferences.spacing;
  root.dataset.compassMotion = preferences.motion;
  root.dataset.compassUnderlineLinks = String(preferences.underlineLinks);
}

const AccessibilityPreferencesContext =
  createContext<AccessibilityPreferencesContextValue | null>(null);

export function AccessibilityPreferencesProvider({
  children,
}: {
  children: ReactNode;
}) {
  const preferences = useSyncExternalStore(
    subscribe,
    getClientSnapshot,
    getServerSnapshot,
  );

  useLayoutEffect(() => {
    applyPreferences(preferences);
  }, [preferences]);

  const setTextSize = useCallback(
    (textSize: AccessibilityTextSize) => {
      publishPreferences({ ...preferences, textSize });
    },
    [preferences],
  );

  const setContrast = useCallback(
    (contrast: AccessibilityContrast) => {
      publishPreferences({ ...preferences, contrast });
    },
    [preferences],
  );

  const setSpacing = useCallback(
    (spacing: AccessibilitySpacing) => {
      publishPreferences({ ...preferences, spacing });
    },
    [preferences],
  );

  const setUnderlineLinks = useCallback(
    (underlineLinks: boolean) => {
      publishPreferences({ ...preferences, underlineLinks });
    },
    [preferences],
  );

  const setMotion = useCallback(
    (motion: AccessibilityMotion) => {
      publishPreferences({ ...preferences, motion });
    },
    [preferences],
  );

  const value = useMemo<AccessibilityPreferencesContextValue>(
    () => ({
      preferences,
      setTextSize,
      setContrast,
      setSpacing,
      setUnderlineLinks,
      setMotion,
      restoreDefaults: removeStoredPreferences,
    }),
    [
      preferences,
      setTextSize,
      setContrast,
      setSpacing,
      setUnderlineLinks,
      setMotion,
    ],
  );

  return (
    <AccessibilityPreferencesContext.Provider value={value}>
      {children}
    </AccessibilityPreferencesContext.Provider>
  );
}

export function useAccessibilityPreferences(): AccessibilityPreferencesContextValue {
  const value = useContext(AccessibilityPreferencesContext);
  if (!value) {
    throw new Error(
      "useAccessibilityPreferences must be used inside AccessibilityPreferencesProvider",
    );
  }
  return value;
}
