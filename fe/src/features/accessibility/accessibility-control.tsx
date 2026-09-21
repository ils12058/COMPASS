"use client";

import { Accessibility, RotateCcw, X } from "lucide-react";
import { useRef } from "react";

import {
  type AccessibilityMotion,
  type AccessibilityTextSize,
  useAccessibilityPreferences,
} from "@/features/accessibility/accessibility-provider";

const TEXT_SIZE_OPTIONS: readonly {
  value: AccessibilityTextSize;
  label: string;
}[] = [
  { value: "default", label: "Default" },
  { value: "large", label: "Large" },
  { value: "extra-large", label: "Extra large" },
];

export function AccessibilityControl() {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const {
    preferences,
    restoreDefaults,
    setContrast,
    setMotion,
    setSpacing,
    setTextSize,
    setUnderlineLinks,
  } = useAccessibilityPreferences();

  function openDialog() {
    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }

    dialog.showModal();
    window.requestAnimationFrame(() => headingRef.current?.focus());
  }

  function closeDialog() {
    dialogRef.current?.close();
  }

  function handleDialogClick(event: React.MouseEvent<HTMLDialogElement>) {
    if (event.target === dialogRef.current) {
      closeDialog();
    }
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        aria-label="Accessibility options"
        className="fixed right-[max(1rem,env(safe-area-inset-right))] z-50 inline-flex size-12 items-center justify-center rounded-full border bg-card text-foreground shadow-md transition-[bottom] duration-200"
        style={{
          bottom:
            "calc(var(--compass-status-banner-height, 0px) + max(1rem, env(safe-area-inset-bottom)))",
        }}
        onClick={openDialog}
      >
        <Accessibility aria-hidden="true" className="size-6" />
      </button>

      <dialog
        ref={dialogRef}
        aria-labelledby="accessibility-options-title"
        className="m-auto w-[min(92vw,34rem)] rounded-2xl border bg-card p-0 text-foreground shadow-md backdrop:bg-black/35"
        onClick={handleDialogClick}
        onClose={() => triggerRef.current?.focus()}
      >
        <div className="max-h-[min(80vh,42rem)] overflow-y-auto p-6 sm:p-7">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2
                ref={headingRef}
                id="accessibility-options-title"
                tabIndex={-1}
                className="font-heading text-2xl font-bold"
              >
                Accessibility options
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Adjust how COMPASS looks and moves on this device.
              </p>
            </div>
            <button
              type="button"
              aria-label="Close accessibility options"
              className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg border bg-card"
              onClick={closeDialog}
            >
              <X aria-hidden="true" className="size-5" />
            </button>
          </div>

          <fieldset className="mt-6 space-y-3">
            <legend className="font-semibold">Text size</legend>
            <div className="grid gap-2 sm:grid-cols-3">
              {TEXT_SIZE_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border bg-background px-3 py-2 text-sm"
                >
                  <input
                    type="radio"
                    name="compass-accessibility-text-size"
                    value={option.value}
                    checked={preferences.textSize === option.value}
                    onChange={() => setTextSize(option.value)}
                  />
                  <span>{option.label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="mt-6 divide-y rounded-xl border">
            <AccessibilityToggle
              label="High contrast"
              description="Use stronger text, borders, and controls."
              checked={preferences.contrast === "high"}
              onChange={(checked) => setContrast(checked ? "high" : "default")}
            />
            <AccessibilityToggle
              label="Increased spacing"
              description="Give text more room to breathe."
              checked={preferences.spacing === "relaxed"}
              onChange={(checked) => setSpacing(checked ? "relaxed" : "default")}
            />
            <AccessibilityToggle
              label="Underline links"
              description="Make text links easier to identify."
              checked={preferences.underlineLinks}
              onChange={setUnderlineLinks}
            />
            <AccessibilityToggle
              label="Reduce motion"
              description="Follow device settings, or turn this on to reduce motion further."
              checked={preferences.motion === "reduced"}
              onChange={(checked) => {
                const motion: AccessibilityMotion = checked ? "reduced" : "system";
                setMotion(motion);
              }}
            />
          </div>

          <button
            type="button"
            className="mt-6 inline-flex min-h-10 items-center gap-2 rounded-lg border bg-card px-4 py-2 text-sm font-semibold"
            onClick={restoreDefaults}
          >
            <RotateCcw aria-hidden="true" className="size-4" />
            Restore defaults
          </button>
        </div>
      </dialog>
    </>
  );
}

function AccessibilityToggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-5 p-4">
      <span>
        <span className="block text-sm font-semibold">{label}</span>
        <span className="mt-1 block text-xs leading-5 text-muted-foreground">
          {description}
        </span>
      </span>
      <input
        type="checkbox"
        className="mt-1 size-5 shrink-0"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
    </label>
  );
}
