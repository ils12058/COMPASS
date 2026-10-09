"use client";

import { useEffect, useId, useRef, useState, useSyncExternalStore, type FormEvent, type KeyboardEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import {
  createClientMessageId,
  IDLE_SEND,
  isUncertainSendFailure,
  MESSAGE_BODY_LIMIT,
  MESSAGE_BODY_PROBLEMS,
  messageBodyProblem,
  messageLength,
  nextSendIntent,
  type SendIntent,
  type SendState,
  type SendTarget,
} from "@/features/guidance-messages/guidance-message-send";
import { cn } from "@/lib/utils/cn";

const COUNTER_FROM = MESSAGE_BODY_LIMIT - 500;

const noSubscription = () => () => {};
const usesCommandKey = () => /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const serverUsesCommandKey = () => false;

/**
 * The text-only composer. One intended Message keeps one client_message_id from its first attempt
 * until the backend confirms it: an unconfirmed attempt can only be retried unchanged, and the
 * draft is cleared only after the canonical Message comes back. The textarea stays mounted and
 * focused throughout; it is read-only (not disabled) while a send is unresolved, so focus is kept.
 */
export function GuidanceMessageComposer<TResult>({
  target,
  label,
  send,
  describeError,
  onSent,
  onPendingChange,
  unavailable = null,
}: {
  /** Where this intended Message goes; null while no recipient is chosen. */
  target: SendTarget | null;
  /** The textarea's accessible name, such as "Message to Guidance Office". */
  label: string;
  send: (intent: SendIntent) => Promise<TResult>;
  describeError: (error: unknown) => string;
  onSent?: (result: TResult) => void;
  /** Reports whether an attempt is in flight or waiting for its retry, so recipients can be locked. */
  onPendingChange?: (pending: boolean) => void;
  /**
   * Why the reader cannot send right now, such as a resolved conversation. The draft stays, read-only,
   * so nothing the reader wrote is lost.
   */
  unavailable?: ReactNode;
}) {
  const textareaId = useId();
  const hintId = useId();
  const counterId = useId();
  const errorId = useId();
  const textarea = useRef<HTMLTextAreaElement>(null);
  const form = useRef<HTMLFormElement>(null);
  const [draft, setDraft] = useState("");
  const [sendState, setSendState] = useState<SendState>(IDLE_SEND);
  // The state as of this instant, so a second click before React re-renders cannot start another send.
  const current = useRef<SendState>(IDLE_SEND);
  const [error, setError] = useState<string | null>(null);
  const [editingNotice, setEditingNotice] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const pending = sendState.kind !== "idle";
  const blocked = Boolean(unavailable) || target === null;
  useEffect(() => {
    onPendingChange?.(pending);
  }, [onPendingChange, pending]);

  useUnsavedChangesGuard({
    dirty: draft.trim() !== "" || pending,
    message:
      sendState.kind === "uncertain"
        ? "Your message might not have been sent. Leave anyway?"
        : "Discard your unsent message?",
  });

  function update(next: SendState) {
    current.current = next;
    if (mounted.current) setSendState(next);
  }

  // Send is disabled while it works, which drops focus if Send had it, and Safari moves focus from a
  // clicked button to the page's main region. The composer stays the place to continue, so focus
  // returns to it unless the reader has moved somewhere else.
  function keepFocus() {
    const active = document.activeElement;
    const composer = form.current;
    if (!composer) return;
    if (!active || active.contains(composer) || composer.contains(active)) textarea.current?.focus();
  }

  async function submit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (current.current.kind === "sending" || blocked) return;
    const problem = messageBodyProblem(draft);
    if (problem) {
      setError(MESSAGE_BODY_PROBLEMS[problem]);
      textarea.current?.focus();
      return;
    }
    const intent = nextSendIntent(current.current, target, draft, () => createClientMessageId() ?? "");
    if (!intent) return;
    if (!intent.clientMessageId) {
      setError("This browser cannot send messages securely. Update the browser and try again.");
      return;
    }
    setError(null);
    setEditingNotice(false);
    update({ kind: "sending", intent });
    try {
      const result = await send(intent);
      update(IDLE_SEND);
      if (!mounted.current) return;
      // Cleared only now that the canonical Message exists; the next Message gets a new ID.
      setDraft("");
      keepFocus();
      onSent?.(result);
    } catch (caught) {
      update(isUncertainSendFailure(caught) ? { kind: "uncertain", intent } : IDLE_SEND);
      if (!mounted.current) return;
      setError(describeError(caught));
      keepFocus();
    }
  }

  function setAside() {
    // The reader chose to change the text: the unconfirmed attempt keeps its ID and the edited text
    // becomes a new intended Message with a new one.
    update(IDLE_SEND);
    setError(null);
    setEditingNotice(true);
    textarea.current?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter adds a line; Ctrl+Enter (⌘+Enter on Apple devices) sends.
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && !event.nativeEvent.isComposing) {
      event.preventDefault();
      form.current?.requestSubmit();
    }
  }

  const length = messageLength(draft);
  const tooLong = length > MESSAGE_BODY_LIMIT;
  const showCounter = length >= COUNTER_FROM;
  const shortcut = useSyncExternalStore(noSubscription, usesCommandKey, serverUsesCommandKey) ? "⌘+Enter" : "Ctrl+Enter";
  const describedBy = [error ? errorId : null, hintId, showCounter ? counterId : null].filter(Boolean).join(" ");

  return (
    <form
      ref={form}
      onSubmit={(event) => void submit(event)}
      aria-busy={sendState.kind === "sending"}
      className="border-t border-brand-line bg-surface px-3 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-4"
    >
      {sendState.kind === "uncertain" ? (
        <div role="alert" className="mb-3 rounded-sm border border-warning/40 bg-surface-raised px-3 py-2.5 text-sm">
          <p id={errorId} className="text-warning">{error ?? "Your message could not be confirmed."}</p>
          <p className="mt-1 text-muted">Retry sends this same message again; it will not be posted twice.</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button type="submit">Retry sending</Button>
            <Button type="button" variant="secondary" onClick={setAside}>
              Edit message
            </Button>
          </div>
        </div>
      ) : error ? (
        <p id={errorId} role="alert" className="mb-2 text-sm text-danger">
          {error}
        </p>
      ) : null}
      {editingNotice ? (
        <p role="status" className="mb-2 text-sm text-muted">
          Your edited text will be sent as a new message. If the earlier attempt reached COMPASS, it will
          still appear in this conversation.
        </p>
      ) : null}
      {unavailable ? <div className="mb-2 text-sm text-muted">{unavailable}</div> : null}
      <label htmlFor={textareaId} className="sr-only">
        {label}
      </label>
      <div className="flex items-end gap-2">
        <Textarea
          ref={textarea}
          id={textareaId}
          value={draft}
          rows={2}
          placeholder="Write a message…"
          readOnly={pending || Boolean(unavailable)}
          disabled={target === null}
          aria-invalid={tooLong || undefined}
          aria-describedby={describedBy}
          aria-keyshortcuts="Control+Enter Meta+Enter"
          onKeyDown={onKeyDown}
          onChange={(event) => {
            setDraft(event.target.value);
            if (error && sendState.kind === "idle") setError(null);
          }}
          className={cn(
            "max-h-48 min-h-11 flex-1 resize-none [field-sizing:content]",
            (pending || unavailable) && "bg-surface-muted",
          )}
        />
        <Button type="submit" className="shrink-0" disabled={pending || blocked}>
          {sendState.kind === "sending" ? "Sending…" : "Send"}
        </Button>
      </div>
      <div className="mt-1.5 flex flex-wrap justify-between gap-x-3 text-xs text-muted">
        {/* Touch keyboards have no shortcut; Send is the way there. */}
        <span id={hintId} className="[@media(pointer:coarse)]:hidden">Enter adds a line. {shortcut} sends.</span>
        {showCounter ? (
          <span id={counterId} className={cn(tooLong && "font-semibold text-danger")}>
            {length.toLocaleString("en-PH")} of {MESSAGE_BODY_LIMIT.toLocaleString("en-PH")} characters
          </span>
        ) : null}
      </div>
    </form>
  );
}
