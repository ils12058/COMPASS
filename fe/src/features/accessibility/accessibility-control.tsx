"use client";

import { Accessibility, RotateCcw } from "lucide-react";
import { useId, useRef, useState } from "react";

import {
  DEFAULT_ACCESSIBILITY_PREFERENCES,
  isDefaultAccessibility,
  type AccessibilityPreferences,
  type AccessibilitySwitch,
  type TextSize,
} from "@/features/accessibility/accessibility-preferences";
import {
  updateAccessibilityPreferences,
  useAccessibilityPreferences,
} from "@/features/accessibility/use-accessibility-preferences";
import { cn } from "@/lib/utils/cn";

const TEXT_SIZE_OPTIONS: readonly { value: TextSize; label: string }[] = [
  { value: "default", label: "Default" },
  { value: "large", label: "Large" },
  { value: "extra-large", label: "Extra large" },
];

const SWITCHES: readonly { key: AccessibilitySwitch; label: string; description: string }[] = [
  {
    key: "relaxedSpacing",
    label: "More spacing",
    description: "More room between lines, letters, and words.",
  },
  {
    key: "underlineLinks",
    label: "Underline links",
    description: "Make every link easy to spot.",
  },
  {
    key: "reduceMotion",
    label: "Reduce motion",
    description: "Stop animations, including the home page headline.",
  },
];

type Placement = "floating" | "header";

const triggerStyles: Record<Placement, string> = {
  floating:
    "fixed bottom-4 right-4 z-40 inline-flex size-12 items-center justify-center rounded-full border border-brand bg-surface-raised text-brand shadow-md transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 print:hidden",
  header:
    "relative inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-md text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus aria-expanded:bg-surface-muted aria-expanded:text-brand",
};

// Popovers sit in the top layer: the floating panel is fixed above its button, and the header
// panel is positioned against the page, just below the portal header.
const panelStyles: Record<Placement, string> = {
  floating: "fixed bottom-20 right-4 origin-bottom-right",
  header: "absolute top-20 right-4 origin-top-right sm:right-6 lg:right-8",
};

export function AccessibilityControl({ placement }: { placement: Placement }) {
  const preferences = useAccessibilityPreferences();
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const titleId = useId();
  const textSizeName = useId();

  function setTextSize(textSize: TextSize) {
    updateAccessibilityPreferences({ ...preferences, textSize });
  }

  function setSwitch(key: AccessibilitySwitch, value: boolean) {
    const next: AccessibilityPreferences = { ...preferences };
    next[key] = value;
    updateAccessibilityPreferences(next);
  }

  return (
    <>
      <button
        type="button"
        popoverTarget={panelId}
        aria-controls={panelId}
        aria-expanded={open}
        aria-label="Accessibility settings"
        title="Accessibility settings"
        className={triggerStyles[placement]}
      >
        <Accessibility size={placement === "header" ? 20 : 22} aria-hidden="true" />
      </button>

      <div
        ref={panelRef}
        id={panelId}
        popover="auto"
        role="dialog"
        aria-labelledby={titleId}
        onToggle={(event) => {
          const isOpen = event.newState === "open";
          setOpen(isOpen);
          if (isOpen) panelRef.current?.querySelector<HTMLInputElement>("input:checked")?.focus();
        }}
        className={cn(
          "inset-auto m-0 max-h-[calc(100dvh-7rem)] w-[min(21rem,calc(100vw-2rem))] overflow-y-auto rounded-md border border-border bg-surface-raised p-5 text-ink shadow-dialog",
          "scale-95 opacity-0 transition-[opacity,scale,overlay,display] transition-discrete duration-150 ease-out open:scale-100 open:opacity-100 starting:open:scale-95 starting:open:opacity-0",
          panelStyles[placement],
        )}
      >
        <h2 id={titleId} className="font-heading text-lg font-bold text-ink">
          Accessibility
        </h2>
        <p className="mt-1 text-xs leading-5 text-muted">Saved in this browser only.</p>

        <fieldset className="mt-4">
          <legend className="text-sm font-semibold text-ink">Text size</legend>
          <div className="mt-2 grid grid-cols-3 gap-1 rounded-md border border-border p-1">
            {TEXT_SIZE_OPTIONS.map((option) => (
              <label key={option.value} className="relative">
                <input
                  type="radio"
                  name={textSizeName}
                  value={option.value}
                  checked={preferences.textSize === option.value}
                  onChange={() => setTextSize(option.value)}
                  className="peer sr-only"
                />
                <span className="flex min-h-10 cursor-pointer items-center justify-center rounded-sm px-2 text-center text-xs font-semibold text-muted transition-colors hover:bg-surface-muted peer-checked:bg-brand peer-checked:text-on-brand peer-focus-visible:ring-2 peer-focus-visible:ring-focus">
                  {option.label}
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="mt-4 divide-y divide-border border-y border-border">
          {SWITCHES.map((item) => (
            <label key={item.key} className="flex cursor-pointer items-center justify-between gap-4 py-3">
              <span>
                <span className="block text-sm font-semibold text-ink">{item.label}</span>
                <span className="block text-xs leading-5 text-muted">{item.description}</span>
              </span>
              <input
                type="checkbox"
                role="switch"
                checked={preferences[item.key]}
                onChange={(event) => setSwitch(item.key, event.target.checked)}
                className="peer sr-only"
              />
              <span
                aria-hidden="true"
                className="relative h-6 w-10 shrink-0 rounded-full bg-border-strong transition-colors after:absolute after:left-0.5 after:top-0.5 after:size-5 after:rounded-full after:bg-surface-raised after:transition-[translate] peer-checked:bg-brand peer-checked:after:translate-x-4 peer-focus-visible:ring-2 peer-focus-visible:ring-focus peer-focus-visible:ring-offset-2"
              />
            </label>
          ))}
        </div>

        <button
          type="button"
          onClick={() => updateAccessibilityPreferences({ ...DEFAULT_ACCESSIBILITY_PREFERENCES })}
          disabled={isDefaultAccessibility(preferences)}
          className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:text-muted disabled:no-underline"
        >
          <RotateCcw size={16} aria-hidden="true" />
          Restore defaults
        </button>
      </div>
    </>
  );
}
