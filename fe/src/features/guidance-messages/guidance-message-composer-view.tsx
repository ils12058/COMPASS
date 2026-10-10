"use client";

import { FileText } from "lucide-react";
import { useId, useRef, useState, useSyncExternalStore, type KeyboardEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { MessageComposerController } from "@/features/guidance-messages/guidance-message-composer";
import { MESSAGE_BODY_LIMIT, messageLength } from "@/features/guidance-messages/guidance-message-send";
import { MessageTemplatePicker } from "@/features/guidance-messages/guidance-message-template-picker";
import { cn } from "@/lib/utils/cn";

const COUNTER_FROM = MESSAGE_BODY_LIMIT - 500;

const noSubscription = () => () => {};
const usesCommandKey = () => /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const serverUsesCommandKey = () => false;

/** Message templates in a staff composer (ADR-104). Students never get them. */
export type MessageTemplatesOption = { canManage: boolean } | null;

/**
 * The text-only composer form. The textarea stays mounted and focused throughout; it is read-only
 * (not disabled) while a send is unresolved, so focus is kept.
 */
export function MessageComposerView({
  controller,
  label,
  unavailable = null,
  templates = null,
  className,
}: {
  controller: MessageComposerController;
  label: string;
  unavailable?: ReactNode;
  templates?: MessageTemplatesOption;
  className?: string;
}) {
  const [choosing, setChoosing] = useState(false);
  const templatesButtonRef = useRef<HTMLButtonElement>(null);
  const textareaId = useId();
  const hintId = useId();
  const counterId = useId();
  const errorId = useId();
  const {
    draft, setDraft, sendState, error, clearError, editingNotice, pending, disabled, blocked, submit, setAside,
    requestSubmit, insertTemplate, focusDraft, attachForm, attachTextarea,
  } = controller;
  // An unconfirmed send owns its exact text until it is retried or deliberately set aside.
  const templatesUnavailable = pending || blocked || Boolean(unavailable);
  if (choosing && templatesUnavailable) setChoosing(false);
  const shortcut = useSyncExternalStore(noSubscription, usesCommandKey, serverUsesCommandKey) ? "⌘+Enter" : "Ctrl+Enter";

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter adds a line; Ctrl+Enter (⌘+Enter on Apple devices) sends.
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && !event.nativeEvent.isComposing) {
      event.preventDefault();
      requestSubmit();
    }
  }

  const length = messageLength(draft);
  const tooLong = length > MESSAGE_BODY_LIMIT;
  const showCounter = length >= COUNTER_FROM;
  const describedBy = [error ? errorId : null, hintId, showCounter ? counterId : null].filter(Boolean).join(" ");

  return (
    <>
      <form
        ref={attachForm}
        onSubmit={(event) => void submit(event)}
        aria-busy={sendState.kind === "sending"}
        className={cn("border-t border-brand-line bg-surface px-3 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-4", className)}
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
        {templates ? (
          <div className="mb-2 flex">
            <Button
              ref={templatesButtonRef}
              variant="secondary"
              className="px-3"
              aria-haspopup="dialog"
              disabled={templatesUnavailable}
              onClick={() => setChoosing(true)}
            >
              <FileText size={16} aria-hidden="true" />
              Templates
            </Button>
          </div>
        ) : null}
        <label htmlFor={textareaId} className="sr-only">
          {label}
        </label>
        <div className="flex items-end gap-2">
          <Textarea
            ref={attachTextarea}
            id={textareaId}
            value={draft}
            rows={2}
            placeholder="Write a message…"
            readOnly={pending || Boolean(unavailable)}
            disabled={disabled}
            aria-invalid={tooLong || undefined}
            aria-describedby={describedBy}
            aria-keyshortcuts="Control+Enter Meta+Enter"
            onKeyDown={onKeyDown}
            onChange={(event) => {
              setDraft(event.target.value);
              if (error && sendState.kind === "idle") clearError();
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
      {/* Outside the form: the picker's own search must never submit the Message. */}
      {templates ? (
        <MessageTemplatePicker
          open={choosing}
          onOpenChange={setChoosing}
          canManage={templates.canManage}
          onChoose={insertTemplate}
          onInserted={focusDraft}
          onDismissed={() => templatesButtonRef.current?.focus()}
        />
      ) : null}
    </>
  );
}
