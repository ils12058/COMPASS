"use client";

import { PageAction } from "@/components/ui/page-action";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, MessageCircle, X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import {
  contextualHintScope,
  reconcileAppointmentMessages,
  useAppointmentMessagesContext,
  useSendAppointmentMessage,
} from "@/features/guidance-messages/guidance-appointment-context";
import {
  ComposerNote,
  ConversationHistoryRegion,
  ResolvedBadge,
  ResolvedNote,
  ThreadStatusControl,
  useThreadConversation,
} from "@/features/guidance-messages/guidance-conversation-surface";
import { useMessageComposer, type MessageComposerController } from "@/features/guidance-messages/guidance-message-composer";
import { MessageComposerView } from "@/features/guidance-messages/guidance-message-composer-view";
import {
  getGuidanceMessagesAccess,
  messageTemplatesFor,
  type GuidanceMessagesAccess,
} from "@/features/guidance-messages/guidance-messages-access";
import { describeSendError } from "@/features/guidance-messages/guidance-messages-errors";
import { changedThreadId, useMessagesFreshness } from "@/features/guidance-messages/guidance-messages-freshness";
import { threadTitle, unreadLabel, type GuidanceViewer } from "@/features/guidance-messages/guidance-messages-presentation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useRealtimeEvent } from "@/features/realtime/realtime-provider";
import { useGuidanceMessagesGetThread } from "@/lib/api/generated/guidance-messages/guidance-messages";
import type { GuidanceThreadResponse } from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";

// Contextual Guidance Messages (ADR-103): the Appointment's one Counseling thread, opened beside
// the work on an Appointment, Counseling or E-Counseling page. It is the same thread as in
// /portal/messages, read and written through the same pieces; only the frame differs. Wide pages
// dock it beside the work without taking focus away; narrow pages open it as a full-width drawer.
//
// The draft and any unconfirmed send live here, above the panel, so closing the panel or moving
// between the dock and the drawer never loses them. The page's own content always stays at the same
// place in the tree, so opening Messages never remounts it (an E-Counseling call stage keeps running).

/** The work area must be at least this wide (rem) to keep the panel beside it. */
const DOCK_MIN_REM = 60;

type ContextualMessagesValue = {
  available: boolean;
  open: boolean;
  unread: number;
  panelId: string;
  toggle: () => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
};

const ContextualMessagesContext = createContext<ContextualMessagesValue | null>(null);

function useDocked(target: RefObject<HTMLElement | null>): boolean {
  const [docked, setDocked] = useState(false);
  useLayoutEffect(() => {
    const element = target.current;
    if (!element) return;
    const measure = () => {
      const rem = Number.parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
      setDocked(element.getBoundingClientRect().width >= DOCK_MIN_REM * rem);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [target]);
  return docked;
}

/**
 * Wraps a page that belongs to one Counseling Appointment. `counterpartName` names the other
 * participant before any thread exists; the backend still decides whether Messages is offered.
 */
export function GuidanceContextualMessages({
  appointmentId,
  counterpartName,
  enabled,
  children,
}: {
  appointmentId: string;
  counterpartName: string;
  /** False where the page has no canonical Counseling Appointment. */
  enabled: boolean;
  children: ReactNode;
}) {
  const { user } = usePortalSession();
  // Keyed by account: another account never inherits a draft, a pending send or an open panel.
  return (
    <ContextualHost
      key={user.id}
      appointmentId={appointmentId}
      counterpartName={counterpartName}
      enabled={enabled}
      access={getGuidanceMessagesAccess(user)}
      currentUserId={user.id}
    >
      {children}
    </ContextualHost>
  );
}

function ContextualHost({
  appointmentId,
  counterpartName,
  enabled,
  access,
  currentUserId,
  children,
}: {
  appointmentId: string;
  counterpartName: string;
  enabled: boolean;
  access: GuidanceMessagesAccess;
  currentUserId: string;
  children: ReactNode;
}) {
  const queryClient = useQueryClient();
  const layoutRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const latestPinRef = useRef<number | null>(null);
  const panelId = useId();
  const [requestedOpen, setRequestedOpen] = useState(false);
  const docked = useDocked(layoutRef);
  const { query, threadId, contextThread, canStart, available } = useAppointmentMessagesContext(
    appointmentId,
    enabled && access.hasWorkspace,
  );
  // A context that is no longer offered closes the panel.
  const open = requestedOpen && available;

  // The panel keeps the thread detail fresh; this only reads it, never fetches it.
  const detail = useGuidanceMessagesGetThread(threadId ?? "", { query: { enabled: false } });
  const thread: GuidanceThreadResponse | null =
    detail.data && detail.dataUpdatedAt >= query.dataUpdatedAt ? detail.data.data : contextThread ?? detail.data?.data ?? null;
  const canSend = access.canWrite && (thread ? thread.status === "OPEN" : canStart);

  const send = useSendAppointmentMessage(appointmentId, threadId, latestPinRef);
  const { mutateAsync } = send;
  const composer = useMessageComposer({
    target: `appointment:${appointmentId}`,
    send: mutateAsync,
    describeError: (error) => describeSendError(error, "thread"),
    blocked: !canSend,
  });

  // While closed, keep the unread count beside the Messages button current from hints for this
  // thread only. Nothing is polled and no history is read until the panel opens.
  useRealtimeEvent("messages.thread_changed", (event) => {
    if (open || !threadId || changedThreadId(event) !== threadId) return;
    void reconcileAppointmentMessages(queryClient, appointmentId, null);
  });

  const close = useCallback(() => {
    setRequestedOpen(false);
  }, []);
  const toggle = useCallback(() => setRequestedOpen((current) => !current), []);

  const viewer: GuidanceViewer = access.isStudent ? "student" : "staff";
  const value: ContextualMessagesValue = {
    available,
    open,
    unread: thread?.unread_count ?? 0,
    panelId,
    toggle,
    triggerRef,
  };
  const panel = (mode: "docked" | "drawer") => (
    <ContextualPanel
      mode={mode}
      appointmentId={appointmentId}
      threadId={threadId}
      thread={thread}
      counterpartName={thread ? threadTitle(thread, viewer) : counterpartName}
      access={access}
      viewer={viewer}
      currentUserId={currentUserId}
      composer={composer}
      latestPinRef={latestPinRef}
      onClose={() => {
        close();
        triggerRef.current?.focus();
      }}
    />
  );

  return (
    <ContextualMessagesContext.Provider value={value}>
      <div
        ref={layoutRef}
        className={cn("grid items-start gap-5", open && docked && "grid-cols-[minmax(0,1fr)_minmax(20rem,25rem)]")}
      >
        {/* Always the first child, so the page's own content never remounts. */}
        <div className="min-w-0">{children}</div>
        {open && docked ? (
          <aside
            id={panelId}
            aria-labelledby={`${panelId}-heading`}
            className={cn(
              "sticky top-4 flex min-h-[20rem] min-w-0 flex-col overflow-hidden rounded-sm border border-brand-line bg-surface-raised",
              // Below the top bar, clear of an E-Counseling call dock, the composer always in view.
              "h-[calc(100dvh-6rem-1px)] lg:h-[calc(100dvh-6.5rem-1px)]",
              "[:root:has([data-call-dock])_&]:h-[calc(100dvh-4.75rem-1px-var(--call-dock-clearance))]",
              "lg:[:root:has([data-call-dock])_&]:h-[calc(100dvh-5rem-1px-var(--call-dock-clearance))]",
            )}
          >
            {panel("docked")}
          </aside>
        ) : null}
      </div>
      {open && !docked ? (
        <Dialog open onOpenChange={(next) => { if (!next) close(); }}>
          <DialogContent
            id={panelId}
            closeLabel="Close Messages"
            aria-labelledby={`${panelId}-heading`}
            aria-describedby={undefined}
            className="left-0 top-0 flex h-dvh max-h-dvh w-full max-w-none translate-x-0 translate-y-0 flex-col overflow-hidden overflow-y-hidden rounded-none border-0 p-0"
            onOpenAutoFocus={(event) => {
              event.preventDefault();
              document.getElementById(`${panelId}-heading`)?.focus();
            }}
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              triggerRef.current?.focus();
            }}
          >
            {panel("drawer")}
          </DialogContent>
        </Dialog>
      ) : null}
    </ContextualMessagesContext.Provider>
  );
}

/** The Messages button for the page header. It appears only once the backend offers Messages. */
export function GuidanceMessagesTrigger({ className }: { className?: string }) {
  const context = useContext(ContextualMessagesContext);
  if (!context) return null;
  return <MessagesTriggerButton {...context} className={className} />;
}

function MessagesTriggerButton({
  available,
  open,
  unread,
  panelId,
  toggle,
  triggerRef,
  className,
}: ContextualMessagesValue & { className?: string }) {
  if (!available) return null;
  const unreadText = unreadLabel(unread);
  return (
    <PageAction
      ref={triggerRef}
      icon={MessageCircle}
      variant="secondary"
      label={unreadText ? `Messages ${unreadText}` : "Messages"}
      className={className}
      aria-expanded={open}
      aria-controls={open ? panelId : undefined}
      onClick={toggle}
    />
  );
}

function ContextualPanel({
  mode,
  appointmentId,
  threadId,
  thread,
  counterpartName,
  access,
  viewer,
  currentUserId,
  composer,
  latestPinRef,
  onClose,
}: {
  mode: "docked" | "drawer";
  appointmentId: string;
  threadId: string | null;
  thread: GuidanceThreadResponse | null;
  counterpartName: string;
  access: GuidanceMessagesAccess;
  viewer: GuidanceViewer;
  currentUserId: string;
  composer: MessageComposerController;
  latestPinRef: RefObject<number | null>;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const headingId = `${useContext(ContextualMessagesContext)?.panelId ?? "messages"}-heading`;
  const [status, setStatus] = useState("");
  const state = useThreadConversation({ threadId, active: true, canWrite: access.canWrite, latestPinRef });
  const shown = state.thread ?? thread;
  const resolved = shown?.status === "RESOLVED";

  // While open: the context always (another tab may have started the thread), and the thread itself
  // when it exists. Hints for other threads are ignored once this thread is known.
  useMessagesFreshness({
    reconcile: () => reconcileAppointmentMessages(queryClient, appointmentId, threadId),
    hintScope: (changed) => contextualHintScope(threadId, changed),
  });

  // A thread that became unavailable sends the panel back to the backend's current answer, which
  // closes the panel when Messages is no longer offered here.
  const concealed = Boolean(threadId) && state.concealed;
  useEffect(() => {
    if (concealed) void reconcileAppointmentMessages(queryClient, appointmentId, null);
  }, [appointmentId, concealed, queryClient]);

  // The docked panel takes focus once when it opens; it never holds it there.
  useEffect(() => {
    if (mode === "docked") document.getElementById(headingId)?.focus();
  }, [headingId, mode]);

  const Heading = mode === "drawer" ? DialogTitle : "h2";
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header
        className={cn(
          "flex items-start justify-between gap-3 border-b border-brand-line px-4 py-3",
          mode === "drawer" && "pt-[max(0.75rem,env(safe-area-inset-top))] pr-16",
        )}
      >
        <div className="min-w-0">
          <Heading
            id={headingId}
            tabIndex={-1}
            className="pr-0 font-heading text-lg font-semibold leading-snug text-ink focus:outline-none"
          >
            Messages
          </Heading>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
            <span className="break-words">{counterpartName} · Counseling</span>
            {resolved ? <ResolvedBadge /> : null}
          </p>
        </div>
        <div className="flex shrink-0 items-start gap-1">
          {shown && viewer === "staff" && access.canManageStaff ? (
            <ThreadStatusControl thread={shown} compact onChanged={setStatus} />
          ) : null}
          {mode === "docked" ? (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close Messages"
              className="inline-flex min-h-10 min-w-10 items-center justify-center rounded-md text-muted hover:bg-surface-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              <X size={18} aria-hidden="true" />
            </button>
          ) : null}
        </div>
      </header>
      <p role="status" className="sr-only">{status}</p>
      {threadId ? (
        concealed ? (
          <p className="px-4 py-4 text-sm text-muted">This conversation is no longer available to your account.</p>
        ) : (
          <ConversationHistoryRegion state={state} currentUserId={currentUserId} />
        )
      ) : (
        // No thread exists until the first Message is confirmed; nothing here pretends otherwise.
        <div className="flex min-h-0 flex-1 items-end px-4 py-4">
          <p className="text-sm text-muted">No Messages conversation has started for this Counseling appointment yet.</p>
        </div>
      )}
      {!access.canWrite ? (
        <ComposerNote>You can read this conversation, but your account cannot send messages.</ComposerNote>
      ) : (
        <MessageComposerView
          controller={composer}
          label={`Message to ${counterpartName}`}
          unavailable={resolved && shown ? <ResolvedNote thread={shown} viewer={viewer} /> : null}
          templates={messageTemplatesFor(access)}
          className="sm:px-3"
        />
      )}
      {threadId && !concealed ? (
        <div className="border-t border-border bg-surface px-4 py-2">
          <GuardedPortalLink
            href={`/portal/messages/${threadId}`}
            className="inline-flex min-h-10 items-center gap-1.5 text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Open full conversation
            <ArrowRight size={16} aria-hidden="true" />
          </GuardedPortalLink>
        </div>
      ) : null}
    </div>
  );
}
