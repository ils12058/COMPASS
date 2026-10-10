// Reader preferences for text size, spacing, link underlines, and motion. They are kept in this
// browser only (localStorage), never on the account, and applied as data attributes on <html>
// that globals.css reads. An absent attribute means the default.

export const ACCESSIBILITY_STORAGE_KEY = "compass-accessibility-v1";

export const TEXT_SIZES = ["default", "large", "extra-large"] as const;
export type TextSize = (typeof TEXT_SIZES)[number];

export type AccessibilityPreferences = {
  textSize: TextSize;
  relaxedSpacing: boolean;
  underlineLinks: boolean;
  reduceMotion: boolean;
};

export type AccessibilitySwitch = "relaxedSpacing" | "underlineLinks" | "reduceMotion";

export const DEFAULT_ACCESSIBILITY_PREFERENCES: Readonly<AccessibilityPreferences> = Object.freeze({
  textSize: "default",
  relaxedSpacing: false,
  underlineLinks: false,
  reduceMotion: false,
});

const MAX_STORED_LENGTH = 256;

function isTextSize(value: unknown): value is TextSize {
  return TEXT_SIZES.some((size) => size === value);
}

export function parseAccessibilityPreferences(raw: string | null): AccessibilityPreferences {
  if (!raw || raw.length > MAX_STORED_LENGTH) return { ...DEFAULT_ACCESSIBILITY_PREFERENCES };

  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return { ...DEFAULT_ACCESSIBILITY_PREFERENCES };
    }

    const textSize = "textSize" in value ? value.textSize : undefined;
    return {
      textSize: isTextSize(textSize) ? textSize : "default",
      relaxedSpacing: "relaxedSpacing" in value && value.relaxedSpacing === true,
      underlineLinks: "underlineLinks" in value && value.underlineLinks === true,
      reduceMotion: "reduceMotion" in value && value.reduceMotion === true,
    };
  } catch {
    return { ...DEFAULT_ACCESSIBILITY_PREFERENCES };
  }
}

export function isDefaultAccessibility(preferences: AccessibilityPreferences): boolean {
  return (
    preferences.textSize === DEFAULT_ACCESSIBILITY_PREFERENCES.textSize &&
    preferences.relaxedSpacing === DEFAULT_ACCESSIBILITY_PREFERENCES.relaxedSpacing &&
    preferences.underlineLinks === DEFAULT_ACCESSIBILITY_PREFERENCES.underlineLinks &&
    preferences.reduceMotion === DEFAULT_ACCESSIBILITY_PREFERENCES.reduceMotion
  );
}

export function accessibilityAttributes(
  preferences: AccessibilityPreferences,
): Record<string, string | null> {
  return {
    "data-a11y-text-size": preferences.textSize === "default" ? null : preferences.textSize,
    "data-a11y-spacing": preferences.relaxedSpacing ? "relaxed" : null,
    "data-a11y-links": preferences.underlineLinks ? "underline" : null,
    "data-a11y-motion": preferences.reduceMotion ? "reduce" : null,
  };
}

// Runs in <head> before the first paint, so saved preferences never jump in after load. It
// mirrors parseAccessibilityPreferences and accessibilityAttributes; keep the three in step.
export const ACCESSIBILITY_BOOTSTRAP_SCRIPT = `(function(){try{var p=JSON.parse(localStorage.getItem(${JSON.stringify(
  ACCESSIBILITY_STORAGE_KEY,
)})||"null");if(!p||typeof p!=="object")return;var r=document.documentElement;if(p.textSize==="large"||p.textSize==="extra-large")r.setAttribute("data-a11y-text-size",p.textSize);if(p.relaxedSpacing===true)r.setAttribute("data-a11y-spacing","relaxed");if(p.underlineLinks===true)r.setAttribute("data-a11y-links","underline");if(p.reduceMotion===true)r.setAttribute("data-a11y-motion","reduce")}catch(e){}})()`;
