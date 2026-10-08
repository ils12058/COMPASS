"use client";

import type { LucideIcon } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/utils/cn";

// How a tile reads at a glance: an ordinary control, something this person turned off (muted mic,
// camera off), a capture that is running and can be stopped, or leaving the call.
export type CallControlTone = "default" | "off" | "live" | "leave";

const tones: Record<CallControlTone, string> = {
  default: "border-border bg-surface-raised text-ink hover:bg-surface-muted",
  off: "border-danger/40 bg-danger/10 text-danger hover:bg-danger/15",
  live: "border-danger bg-surface-raised text-danger hover:bg-danger/10",
  leave: "border-danger bg-danger text-on-brand hover:bg-danger/90",
};

// One square-ish call control: an icon above a short visible label, at least 44px each way. It is
// a feature control for the live call, not the global IconAction (ADR-091 keeps IconAction for
// conventional low-risk actions). The visible label is always part of the accessible name; pass
// `accessibleName` only to say more, for example "Stop recording" for a tile labelled "Stop".
export const CallControl = forwardRef<
  HTMLButtonElement,
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
    icon: LucideIcon;
    label: ReactNode;
    accessibleName?: string;
    tone?: CallControlTone;
    // Marks a device problem on the tile, such as a blocked microphone; the message itself is shown
    // beside the call.
    problem?: boolean;
  }
>(({ icon: Icon, label, accessibleName, tone = "default", problem = false, className, disabled, ...props }, ref) => (
  <button
    ref={ref}
    type="button"
    aria-label={accessibleName}
    disabled={disabled}
    className={cn(
      "relative inline-flex min-h-14 min-w-[3.25rem] max-w-28 flex-auto flex-col items-center justify-center gap-1 rounded-md border px-1.5 py-1.5 text-xs font-semibold leading-tight transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-surface-raised disabled:cursor-not-allowed disabled:opacity-55 motion-reduce:transition-none",
      tones[tone],
      className,
    )}
    {...props}
  >
    <Icon aria-hidden="true" size={20} strokeWidth={2} />
    <span className="max-w-full text-center">{label}</span>
    {problem ? <span aria-hidden="true" className="absolute right-1.5 top-1.5 size-2 rounded-full bg-warning ring-2 ring-surface-raised" /> : null}
  </button>
));
CallControl.displayName = "CallControl";

// The row of call controls under the video. Controls keep their labels and wrap rather than scroll
// sideways; the stage decides which controls belong in it for this person.
export function CallTray({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div role="group" aria-label="Call controls" className={cn("@container/tray flex flex-wrap justify-center gap-1 border-t border-brand-line bg-surface-raised p-1.5 sm:gap-1.5 sm:p-2", className)}>
      {children}
    </div>
  );
}
