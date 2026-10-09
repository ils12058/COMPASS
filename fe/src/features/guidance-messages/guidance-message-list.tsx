"use client";

import { ArrowDown } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";

import { Button } from "@/components/ui/button";
import { messageDayKey, messageDayLabel, messageTime } from "@/features/guidance-messages/guidance-message-time";
import { senderLabel } from "@/features/guidance-messages/guidance-messages-presentation";
import type { GuidanceMessageResponse } from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";

/** Within this distance of the end, the reader counts as reading the newest Message. */
const LATEST_THRESHOLD_PX = 48;
const ANNOUNCEMENT_MS = 4_000;

type DayGroup = { key: string; label: string; messages: GuidanceMessageResponse[] };

function groupByDay(messages: readonly GuidanceMessageResponse[], now: Date): DayGroup[] {
  const groups: DayGroup[] = [];
  for (const message of messages) {
    const key = messageDayKey(message.created_at);
    const group = groups.at(-1);
    if (group && group.key === key) group.messages.push(message);
    else groups.push({ key, label: messageDayLabel(message.created_at, now), messages: [message] });
  }
  return groups;
}

/**
 * The conversation's Messages in chronological order. Opening a conversation shows the newest
 * Message; loading older Messages keeps the reader's place; a new Message keeps a reader who was at
 * the end there, and otherwise offers "New messages" instead of moving them. Bodies are plain text:
 * line breaks are kept and long words wrap; nothing is interpreted as HTML, Markdown or links.
 */
export function GuidanceMessageList({
  threadId,
  messages,
  hasOlder,
  currentUserId,
  loadingOlder,
  olderError,
  onLoadOlder,
  onAtLatestChange,
  latestPinRef,
}: {
  threadId: string;
  messages: readonly GuidanceMessageResponse[];
  hasOlder: boolean;
  currentUserId: string;
  loadingOlder: boolean;
  olderError: string | null;
  onLoadOlder: (anchor: number) => void;
  onAtLatestChange: (atLatest: boolean) => void;
  /** After the reader sends, the list stays at its end until this sequence has arrived. */
  latestPinRef: RefObject<number | null>;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const atLatest = useRef(true);
  // Distance from the end before older Messages were requested, so the reader's place is restored.
  const anchorFromEnd = useRef<number | null>(null);
  const loaded = useRef<{ first: number; last: number } | null>(null);
  const [newBelow, setNewBelow] = useState(false);
  const [announcement, setAnnouncement] = useState("");

  const first = messages[0]?.sequence ?? 0;
  const last = messages.at(-1)?.sequence ?? 0;

  function report(next: boolean) {
    if (atLatest.current === next) return;
    atLatest.current = next;
    onAtLatestChange(next);
  }

  function scrollToLatest() {
    const element = scroller.current;
    if (!element) return;
    element.scrollTop = element.scrollHeight;
    setNewBelow(false);
    report(true);
  }

  useLayoutEffect(() => {
    const element = scroller.current;
    const before = loaded.current;
    loaded.current = { first, last };
    if (!element || last === 0) return;
    if (!before || before.last === 0) {
      scrollToLatest();
      return;
    }
    if (anchorFromEnd.current !== null && first < before.first) {
      element.scrollTop = element.scrollHeight - anchorFromEnd.current;
    }
    if (first !== before.first) anchorFromEnd.current = null;
    if (last <= before.last) return;

    const pinned = latestPinRef.current;
    if (pinned !== null || atLatest.current) {
      scrollToLatest();
      if (pinned !== null && last >= pinned) latestPinRef.current = null;
    } else {
      setNewBelow(true);
    }
    const arrived = messages.filter((message) => message.sequence > before.last && message.sender.id !== currentUserId).length;
    // A short polite notice, never the confidential text itself.
    if (arrived > 0) setAnnouncement(arrived === 1 ? "New message received." : `${arrived} new messages received.`);
    // Only the sequence range decides what changed; the Messages themselves never change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [first, last]);

  useEffect(() => {
    if (!announcement) return;
    const timer = setTimeout(() => setAnnouncement(""), ANNOUNCEMENT_MS);
    return () => clearTimeout(timer);
  }, [announcement]);

  // The Load older control disappears once the start is reached. If it had focus, keep focus in
  // the history instead of dropping it to the page.
  const hadOlder = useRef(hasOlder);
  useEffect(() => {
    const reachedStart = hadOlder.current && !hasOlder;
    hadOlder.current = hasOlder;
    if (reachedStart && document.activeElement === document.body) {
      scroller.current?.focus({ preventScroll: true });
    }
  }, [hasOlder]);

  function onScroll() {
    const element = scroller.current;
    if (!element) return;
    const next = element.scrollHeight - element.scrollTop - element.clientHeight <= LATEST_THRESHOLD_PX;
    if (next) setNewBelow(false);
    report(next);
  }

  function loadOlder() {
    const element = scroller.current;
    if (element) anchorFromEnd.current = element.scrollHeight - element.scrollTop;
    onLoadOlder(first);
  }

  const groups = groupByDay(messages, new Date());

  return (
    <div className="relative min-h-0 flex-1">
      <div
        ref={scroller}
        role="region"
        aria-label="Conversation history"
        tabIndex={0}
        onScroll={onScroll}
        className="absolute inset-0 overflow-y-auto overscroll-contain px-3 py-3 [overflow-anchor:none] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus sm:px-4"
      >
        {/* A short conversation sits at the end, next to the composer. */}
        <div className="flex min-h-full flex-col justify-end">
          <div className="mb-3 flex flex-col items-center gap-2 text-center">
            {hasOlder ? (
              <Button
                variant="secondary"
                className="min-h-10"
                disabled={loadingOlder}
                aria-describedby={olderError ? `${threadId}-older-error` : undefined}
                onClick={loadOlder}
              >
                {loadingOlder ? "Loading older messages…" : "Load older messages"}
              </Button>
            ) : (
              <p className="text-xs text-muted">Start of conversation</p>
            )}
            {olderError ? (
              <p id={`${threadId}-older-error`} role="alert" className="text-sm text-danger">
                {olderError}
              </p>
            ) : null}
          </div>
          {groups.map((group) => (
            <section key={group.key} aria-labelledby={`guidance-day-${group.key}`} className="mt-4 first-of-type:mt-0">
              <h3
                id={`guidance-day-${group.key}`}
                className="mb-3 flex items-center gap-3 text-xs font-semibold text-muted before:h-px before:flex-1 before:bg-border after:h-px after:flex-1 after:bg-border"
              >
                {group.label}
              </h3>
              <ol className="space-y-3">
                {group.messages.map((message, index) => {
                  const own = message.sender.id === currentUserId;
                  const previous = group.messages[index - 1];
                  const showSender = !previous || previous.sender.id !== message.sender.id;
                  const sender = senderLabel(message.sender, currentUserId);
                  return (
                    <li key={message.id} className={cn("flex flex-col", own ? "items-end" : "items-start")}>
                      <p className="mb-1 flex flex-wrap items-baseline gap-x-2 px-1 text-xs text-muted">
                        <span className={cn("font-semibold text-ink", !showSender && "sr-only")}>{sender}</span>
                        <time dateTime={message.created_at}>{messageTime(message.created_at)}</time>
                      </p>
                      <div
                        className={cn(
                          "max-w-[min(40rem,88%)] rounded-md border px-3 py-2 text-sm leading-6 text-ink",
                          own ? "border-brand-line bg-brand-wash" : "border-border bg-surface-muted",
                        )}
                      >
                        <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{message.body}</p>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </section>
          ))}
        </div>
      </div>
      {newBelow ? (
        <button
          type="button"
          onClick={scrollToLatest}
          className="absolute bottom-3 left-1/2 inline-flex min-h-10 -translate-x-1/2 items-center gap-1.5 rounded-md border border-border-strong bg-surface-raised px-3 py-2 text-sm font-semibold text-brand shadow-float focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          <ArrowDown size={16} aria-hidden="true" />
          New messages
        </button>
      ) : null}
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </div>
  );
}
