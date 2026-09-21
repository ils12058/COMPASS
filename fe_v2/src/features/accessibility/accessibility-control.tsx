"use client";

import { Accessibility, RotateCcw } from "lucide-react";

import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import {
  type AccessibilityMotion,
  type AccessibilityTextSize,
  useAccessibilityPreferences,
} from "@/features/accessibility/accessibility-provider";

const TEXT_SIZE_OPTIONS: readonly { value: AccessibilityTextSize; label: string }[] = [
  { value: "default", label: "Default" },
  { value: "large", label: "Large" },
  { value: "extra-large", label: "Extra large" },
];

function ToggleSetting({
  id,
  label,
  description,
  checked,
  onCheckedChange,
}: {
  id: string;
  label: string;
  description: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}) {
  const labelId = `compass-accessibility-${id}-label`;
  const descriptionId = `compass-accessibility-${id}-description`;

  return (
    <div className="compass-accessibility__toggle-setting">
      <div>
        <p className="compass-accessibility__setting-label" id={labelId}>
          {label}
        </p>
        <p className="compass-accessibility__setting-description" id={descriptionId}>
          {description}
        </p>
      </div>
      <Switch
        aria-describedby={descriptionId}
        aria-labelledby={labelId}
        checked={checked}
        onCheckedChange={onCheckedChange}
      />
    </div>
  );
}

export function AccessibilityControl() {
  const {
    preferences,
    restoreDefaults,
    setContrast,
    setMotion,
    setSpacing,
    setTextSize,
    setUnderlineLinks,
  } = useAccessibilityPreferences();

  return (
    <div className="compass-accessibility">
      <Popover>
        <PopoverTrigger
          aria-label="Open accessibility options"
          className="compass-accessibility__trigger"
          type="button"
        >
          <Accessibility aria-hidden="true" />
          <span className="sr-only">Accessibility options</span>
        </PopoverTrigger>
        <PopoverContent
          align="end"
          className="compass-surface compass-accessibility__panel"
          side="top"
          sideOffset={12}
        >
          <PopoverHeader className="compass-accessibility__header">
            <PopoverTitle>Accessibility options</PopoverTitle>
            <PopoverDescription>
              Adjust how COMPASS looks and moves on this device.
            </PopoverDescription>
          </PopoverHeader>

          <fieldset className="compass-accessibility__fieldset">
            <legend>Text size</legend>
            <div className="compass-accessibility__choice-grid">
              {TEXT_SIZE_OPTIONS.map((option) => (
                <label className="compass-accessibility__choice" key={option.value}>
                  <input
                    checked={preferences.textSize === option.value}
                    name="compass-accessibility-text-size"
                    onChange={() => setTextSize(option.value)}
                    type="radio"
                    value={option.value}
                  />
                  <span>{option.label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="compass-accessibility__settings">
            <ToggleSetting
              checked={preferences.contrast === "high"}
              description="Use stronger colors and borders."
              id="contrast"
              label="High contrast"
              onCheckedChange={(checked) => setContrast(checked ? "high" : "default")}
            />
            <ToggleSetting
              checked={preferences.spacing === "relaxed"}
              description="Give text more room to breathe."
              id="spacing"
              label="Increased spacing"
              onCheckedChange={(checked) => setSpacing(checked ? "relaxed" : "default")}
            />
            <ToggleSetting
              checked={preferences.underlineLinks}
              description="Make text links easier to identify."
              id="links"
              label="Underline links"
              onCheckedChange={setUnderlineLinks}
            />
            <ToggleSetting
              checked={preferences.motion === "reduced"}
              description="Follow device settings, or turn this on to reduce motion further."
              id="motion"
              label="Reduce motion"
              onCheckedChange={(checked) => {
                const motion: AccessibilityMotion = checked ? "reduced" : "system";
                setMotion(motion);
              }}
            />
          </div>

          <button className="compass-accessibility__reset" onClick={restoreDefaults} type="button">
            <RotateCcw aria-hidden="true" />
            Restore defaults
          </button>
        </PopoverContent>
      </Popover>
    </div>
  );
}
