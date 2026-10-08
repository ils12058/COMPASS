"use client";

import { Columns2, PanelLeft, RectangleHorizontal, type LucideIcon } from "lucide-react";
import { useLayoutEffect, useState, type RefObject } from "react";

import { cn } from "@/lib/utils/cn";

// Named densities for the Counselor's wide session workspace (ADR-093). Presets, not a drag
// splitter: each is predictable, keyboard operable and keeps the video's aspect ratio.
export type LayoutPreset = "compact" | "balanced" | "focus";

const presets: Array<{ value: LayoutPreset; label: string; icon: LucideIcon }> = [
  { value: "compact", label: "Compact", icon: PanelLeft },
  { value: "balanced", label: "Balanced", icon: Columns2 },
  { value: "focus", label: "Focus", icon: RectangleHorizontal },
];

// Two columns start at the workspace's own width (a container query), so an expanded dock stacks
// them instead of squeezing the video. Compact narrows the call toward a usable minimum and widens
// the work; Focus gives the call the full width and moves the work below it.
export const sessionGrid: Record<LayoutPreset, string> = {
  compact: "@4xl:grid-cols-[minmax(20rem,2fr)_minmax(0,3fr)]",
  balanced: "@4xl:grid-cols-2",
  focus: "grid-cols-1",
};

// The call stays in view beside work that scrolls with the page; in Focus it scrolls normally.
export const sessionStageClass: Record<LayoutPreset, string> = {
  compact: "@4xl:sticky @4xl:top-4",
  balanced: "@4xl:sticky @4xl:top-4",
  focus: "",
};

// On a phone the call uses the full width of the screen.
export const phoneBleed = "-mx-4 rounded-none border-x-0 sm:mx-0 sm:rounded-sm sm:border-x";

// The workspace width at which the presets apply, in rem (Tailwind's @4xl).
const WIDE_WORKSPACE_REM = 56;

// Whether the workspace is wide enough for two columns. It decides which secondary sections start
// open; the layout itself is pure CSS.
export function useWideWorkspace(target: RefObject<HTMLElement | null>): boolean {
  const [wide, setWide] = useState(false);
  useLayoutEffect(() => {
    const element = target.current;
    if (!element) return;
    const measure = () => {
      const rem = Number.parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
      setWide(element.getBoundingClientRect().width >= WIDE_WORKSPACE_REM * rem);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [target]);
  return wide;
}

// A single-choice group of three named presets. Each is a toggle button with a visible name, so
// the current layout is announced and never depends on reading the icon.
export function LayoutPresetControl({
  value,
  onChange,
  className,
}: {
  value: LayoutPreset;
  onChange: (value: LayoutPreset) => void;
  className?: string;
}) {
  return (
    <div role="group" aria-label="Session layout" className={cn("inline-flex rounded-md border border-border bg-surface-raised p-0.5", className)}>
      {presets.map(({ value: preset, label, icon: Icon }) => (
        <button
          key={preset}
          type="button"
          aria-pressed={value === preset}
          onClick={() => onChange(preset)}
          className={cn(
            "inline-flex min-h-10 items-center gap-1.5 rounded-[calc(var(--radius-md)-2px)] px-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus motion-reduce:transition-none",
            value === preset ? "bg-brand text-on-brand" : "text-muted hover:bg-surface-muted hover:text-ink",
          )}
        >
          <Icon aria-hidden="true" size={16} />
          {label}
        </button>
      ))}
    </div>
  );
}
