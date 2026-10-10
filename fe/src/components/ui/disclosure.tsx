"use client";

import { ChevronRight } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils/cn";

// Progressive disclosure for settled detail and longer explanation (ADR-091, ADR-093). Never put
// what a reader must notice or decide behind one: active recording or transcription, a pending
// decision, a failure, or the consequence of an action at the moment it is confirmed.

// Open state that the reader controls, reset when the surrounding layout changes what should be
// open by default (for example, a denser layout preset collapsing secondary work).
function useDisclosureState(defaultOpen: boolean, open?: boolean, onOpenChange?: (open: boolean) => void) {
  const [ownOpen, setOwnOpen] = useState(defaultOpen);
  const [previousDefault, setPreviousDefault] = useState(defaultOpen);
  if (previousDefault !== defaultOpen) {
    setPreviousDefault(defaultOpen);
    setOwnOpen(defaultOpen);
  }
  const current = open ?? ownOpen;
  return [current, (next: boolean) => {
    if (open === undefined) setOwnOpen(next);
    onOpenChange?.(next);
  }] as const;
}

// An inline "Details" disclosure inside a row or paragraph group, on the native <details> element:
// keyboard and tap activation, the expanded state for assistive technology and find-in-page
// expansion come from the browser. Closed content stays mounted.
export function Disclosure({
  summary,
  children,
  defaultOpen = false,
  open,
  onOpenChange,
  className,
  summaryClassName,
  contentClassName,
}: {
  summary: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  className?: string;
  summaryClassName?: string;
  contentClassName?: string;
}) {
  const contentId = useId();
  const [current, setCurrent] = useDisclosureState(defaultOpen, open, onOpenChange);
  return (
    <details
      className={cn("group/disclosure", className)}
      open={current}
      onToggle={(event) => {
        if (event.currentTarget.open !== current) setCurrent(event.currentTarget.open);
      }}
    >
      <summary
        aria-controls={contentId}
        className={cn(
          "inline-flex min-h-11 cursor-pointer list-none items-center gap-1 rounded-md text-sm font-semibold text-brand hover:text-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus [&::-webkit-details-marker]:hidden",
          summaryClassName,
        )}
      >
        <ChevronRight
          aria-hidden="true"
          size={16}
          className="shrink-0 transition-transform group-open/disclosure:rotate-90 motion-reduce:transition-none"
        />
        {summary}
      </summary>
      <div id={contentId} className={contentClassName}>
        {children}
      </div>
    </details>
  );
}

// A named section that can collapse, such as secondary work beside a live session. It sits on the
// canvas like an accordion row, so the surfaces inside it stay the only frames. The heading keeps its
// level for heading navigation and holds the toggle button (the disclosure pattern of the WAI-ARIA
// practices). `status` is the one-line state that stays visible while it is collapsed, so collapsing
// never hides the section's state. Closed content stays mounted, so its own state, such as a
// selected tab or an unsaved draft, survives.
export function DisclosureSection({
  title,
  status,
  children,
  defaultOpen = false,
  open,
  onOpenChange,
  level = 2,
  className,
  contentClassName,
}: {
  title: string;
  status?: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  level?: 2 | 3;
  className?: string;
  contentClassName?: string;
}) {
  const id = useId();
  const headingId = `${id}-heading`;
  const contentId = `${id}-content`;
  const [current, setCurrent] = useDisclosureState(defaultOpen, open, onOpenChange);
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <section aria-labelledby={headingId} className={cn("min-w-0", className)}>
      <Heading id={headingId} className="font-heading text-base font-semibold text-ink">
        <button
          type="button"
          aria-expanded={current}
          aria-controls={contentId}
          onClick={() => setCurrent(!current)}
          className="flex min-h-12 w-full items-center gap-2 rounded-sm border-b border-brand-line px-1 py-2 text-left hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          <ChevronRight
            aria-hidden="true"
            size={18}
            className={cn("shrink-0 text-muted transition-transform motion-reduce:transition-none", current && "rotate-90")}
          />
          {/* The status moves under the title when both don't fit on one line. */}
          <span className="flex min-w-0 flex-1 flex-wrap items-baseline justify-between gap-x-3">
            <span>{title}</span>
            {status ? <span className="font-sans text-sm font-medium text-muted">{status}</span> : null}
          </span>
        </button>
      </Heading>
      <div id={contentId} hidden={!current} className={cn("pb-2 pt-3", contentClassName)}>
        {children}
      </div>
    </section>
  );
}
