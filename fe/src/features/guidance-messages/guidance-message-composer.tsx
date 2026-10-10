"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import { MessageComposerView, type MessageTemplatesOption } from "@/features/guidance-messages/guidance-message-composer-view";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import {
  createClientMessageId,
  IDLE_SEND,
  isUncertainSendFailure,
  MESSAGE_BODY_PROBLEMS,
  messageBodyProblem,
  nextSendIntent,
  type SendIntent,
  type SendState,
  type SendTarget,
} from "@/features/guidance-messages/guidance-message-send";
import {
  insertTemplateText,
  templateInsertProblem,
  type TemplateInsertResult,
} from "@/features/guidance-messages/guidance-message-templates";

export type MessageComposerOptions<TResult> = {
  /** Where this intended Message goes; null while no recipient is chosen. */
  target: SendTarget | null;
  send: (intent: SendIntent) => Promise<TResult>;
  describeError: (error: unknown) => string;
  onSent?: (result: TResult) => void;
  /** True while the reader cannot send, such as in a resolved conversation. The draft is kept. */
  blocked?: boolean;
};

export type MessageComposerController = {
  draft: string;
  setDraft: (value: string) => void;
  sendState: SendState;
  error: string | null;
  clearError: () => void;
  editingNotice: boolean;
  pending: boolean;
  disabled: boolean;
  blocked: boolean;
  submit: (event?: FormEvent<HTMLFormElement>) => Promise<void>;
  setAside: () => void;
  /** Submits through the form, as Ctrl/⌘+Enter does. */
  requestSubmit: () => void;
  /**
   * Inserts a Message template's text into the draft (ADR-104). It never sends and never creates a
   * client_message_id. Refused, with the draft unchanged, while a send is in flight or unconfirmed
   * (that text belongs to its retry) or when the result would be too long.
   */
  insertTemplate: (body: string) => TemplateInsertResult;
  /** Moves focus to the end of the draft, such as after a template was inserted. */
  focusDraft: () => void;
  /** Callback refs for the view that currently shows this composer, if any. */
  attachTextarea: (element: HTMLTextAreaElement | null) => void;
  attachForm: (element: HTMLFormElement | null) => void;
};

/**
 * The state of one composer: its draft and the send intent (ADR-102). One intended Message keeps
 * one client_message_id from its first attempt until the backend confirms it: an unconfirmed
 * attempt can only be retried unchanged, and the draft is cleared only after the canonical Message
 * comes back. A page that shows its composer only some of the time, such as a contextual Messages
 * panel, owns this state above the panel, so closing the panel loses neither the draft nor an
 * unconfirmed send. A nonblank or unconfirmed draft guards portal navigation.
 */
export function useMessageComposer<TResult>({
  target,
  send,
  describeError,
  onSent,
  blocked: unavailable = false,
}: MessageComposerOptions<TResult>): MessageComposerController {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
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
  const blocked = unavailable || target === null;

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
    const composer = formRef.current;
    if (!composer) return;
    if (!active || active.contains(composer) || composer.contains(active)) textareaRef.current?.focus();
  }

  async function submit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (current.current.kind === "sending" || blocked || target === null) return;
    const problem = messageBodyProblem(draft);
    if (problem) {
      setError(MESSAGE_BODY_PROBLEMS[problem]);
      textareaRef.current?.focus();
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

  const attachTextarea = useCallback((element: HTMLTextAreaElement | null) => {
    textareaRef.current = element;
  }, []);
  const attachForm = useCallback((element: HTMLFormElement | null) => {
    formRef.current = element;
  }, []);

  function insertTemplate(body: string): TemplateInsertResult {
    if (current.current.kind !== "idle" || blocked) return "unavailable";
    if (templateInsertProblem(draft, body)) return "too_long";
    setDraft(insertTemplateText(draft, body));
    setError(null);
    return "inserted";
  }

  function focusDraft() {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.focus();
    const end = textarea.value.length;
    textarea.setSelectionRange(end, end);
    textarea.scrollTop = textarea.scrollHeight;
  }

  function setAside() {
    // The reader chose to change the text: the unconfirmed attempt keeps its ID and the edited text
    // becomes a new intended Message with a new one.
    update(IDLE_SEND);
    setError(null);
    setEditingNotice(true);
    textareaRef.current?.focus();
  }

  return {
    draft,
    setDraft,
    sendState,
    error,
    clearError: () => setError(null),
    editingNotice,
    pending,
    disabled: target === null,
    blocked,
    submit,
    setAside,
    requestSubmit: () => formRef.current?.requestSubmit(),
    insertTemplate,
    focusDraft,
    attachTextarea,
    attachForm,
  };
}

/** A composer with its own state, for pages that always show it. */
export function GuidanceMessageComposer<TResult>({
  label,
  unavailable = null,
  onPendingChange,
  templates,
  ...options
}: Omit<MessageComposerOptions<TResult>, "blocked"> & {
  /** Offers Message templates; staff only. */
  templates?: MessageTemplatesOption;
  /** The textarea's accessible name, such as "Message to Guidance Office". */
  label: string;
  /**
   * Why the reader cannot send right now, such as a resolved conversation. The draft stays, read-only,
   * so nothing the reader wrote is lost.
   */
  unavailable?: ReactNode;
  /** Reports whether an attempt is in flight or waiting for its retry, so recipients can be locked. */
  onPendingChange?: (pending: boolean) => void;
}) {
  const controller = useMessageComposer({ ...options, blocked: Boolean(unavailable) });
  const { pending } = controller;
  useEffect(() => {
    onPendingChange?.(pending);
  }, [onPendingChange, pending]);
  return <MessageComposerView controller={controller} label={label} unavailable={unavailable} templates={templates} />;
}
