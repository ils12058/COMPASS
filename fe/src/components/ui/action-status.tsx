"use client";

import { CheckCircle2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

// A short, non-blocking confirmation that a routine change was saved: "Weekly schedule saved.",
// "Profile changes saved." It appears only after the backend confirmed the change, floats at the
// bottom right of the workspace (above a collection's floating tools when they are on the page),
// is announced politely, never takes focus, and leaves after a few seconds or when dismissed.
//
// It is never the only place a failure, a stale-state conflict, an uncertain result, or anything
// the reader must act on is shown: those stay in context, beside the work. Consequential actions
// confirm inside their own dialog instead (ConsequentialActionDialog `completed`).
export const ACTION_STATUS_DURATION_MS = 5000;

export type ActionStatusMessage = { id: number; text: string };

// One message per owning surface: a newer one replaces it instead of stacking.
export function nextActionStatus(current: ActionStatusMessage | null, text: string): ActionStatusMessage {
  return { id: (current?.id ?? 0) + 1, text };
}

// The dismissal clock, kept free of React so it can be tested with fake timers. Pausing (while the
// pointer or keyboard focus is on the status) stops it; resuming gives the reader the full time
// again.
export function createDismissTimer(onElapse: () => void, durationMs = ACTION_STATUS_DURATION_MS) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const clear = () => {
    if (timer !== undefined) clearTimeout(timer);
    timer = undefined;
  };
  return {
    start() {
      clear();
      timer = setTimeout(() => {
        timer = undefined;
        onElapse();
      }, durationMs);
    },
    clear,
    get running() {
      return timer !== undefined;
    },
  };
}

export function useActionStatus() {
  const [status, setStatus] = useState<ActionStatusMessage | null>(null);
  const show = useCallback((text: string) => setStatus((current) => nextActionStatus(current, text)), []);
  const dismiss = useCallback(() => setStatus(null), []);
  return { status, show, dismiss };
}

export function ActionStatus({
  status,
  onDismiss,
}: {
  status: ActionStatusMessage | null;
  onDismiss: () => void;
}) {
  const [paused, setPaused] = useState(false);
  // Where focus was before the reader moved into the status, so dismissing it from the keyboard
  // does not drop focus to the page.
  const focusOrigin = useRef<HTMLElement | null>(null);
  const onDismissRef = useRef(onDismiss);
  useEffect(() => {
    onDismissRef.current = onDismiss;
  }, [onDismiss]);

  useEffect(() => {
    if (!status || paused) return;
    const timer = createDismissTimer(() => onDismissRef.current());
    timer.start();
    return timer.clear;
  }, [status, paused]);

  return (
    // The status element stays mounted, so each new message is announced when it is inserted.
    <div
      data-action-status=""
      className="pointer-events-none fixed inset-x-4 bottom-(--action-status-offset) z-40 flex justify-end sm:left-auto sm:right-6 lg:right-8 print:hidden"
    >
      <div
        className={
          status
            ? "pointer-events-auto flex min-h-11 max-w-md animate-[action-status-in_160ms_ease-out] items-center gap-2 rounded-md border border-success/35 bg-surface-raised py-1 pl-3 pr-1 shadow-float"
            : "sr-only"
        }
        onPointerEnter={() => setPaused(true)}
        onPointerLeave={() => setPaused(false)}
        onFocus={(event) => {
          setPaused(true);
          if (!event.currentTarget.contains(event.relatedTarget) && event.relatedTarget instanceof HTMLElement) {
            focusOrigin.current = event.relatedTarget;
          }
        }}
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) setPaused(false);
        }}
      >
        {status ? <CheckCircle2 size={18} aria-hidden="true" className="shrink-0 text-success" /> : null}
        <p role="status" className="min-w-0 flex-1 text-sm font-medium leading-5 text-ink">
          {status ? <span key={status.id}>{status.text}</span> : null}
        </p>
        {status ? (
          <button
            type="button"
            aria-label="Dismiss message"
            onClick={() => {
              const origin = focusOrigin.current;
              focusOrigin.current = null;
              onDismiss();
              if (origin?.isConnected) origin.focus();
            }}
            className="inline-flex min-h-10 min-w-10 shrink-0 items-center justify-center rounded-md text-muted hover:bg-surface-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            <X size={16} aria-hidden="true" />
          </button>
        ) : null}
      </div>
    </div>
  );
}
