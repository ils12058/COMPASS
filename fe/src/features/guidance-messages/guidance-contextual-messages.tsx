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
  reconcileCaseCoordinationMessages,
  useCaseCoordinationMessagesContext,
  useSendCaseCoordinationMessage,
} from "@/features/guidance-messages/guidance-case-coordination-context";
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
import { describeSendError, type GuidanceSendContext } from "@/features/guidance-messages/guidance-messages-errors";
import { changedThreadId, useMessagesFreshness, type MessagesRefreshScope } from "@/features/guidance-messages/guidance-messages-freshness";
import {
  CASE_COORDINATION_ENDED_COPY,
  CASE_COORDINATION_ENTRY_COPY,
  personName,
  threadTitle,
  unreadLabel,
  type GuidanceViewer,
} from "@/features/guidance-messages/guidance-messages-presentation";
import type { SendIntent } from "@/features/guidance-messages/guidance-message-send";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useRealtimeEvent } from "@/features/realtime/realtime-provider";
import { useGuidanceMessagesGetThread } from "@/lib/api/generated/guidance-messages/guidance-messages";
import type { GuidanceOpenResponse, GuidanceThreadResponse } from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";

// Contextual Guidance Messages (ADR-103): one Counseling conversation opened beside the work on a
// page. Appointment and case-coordination targets share this one shell — dock/drawer, composer,
// paging, read rules, focus and realtime — while each wrapper owns only its context hook and send
// mutation. It is always the same thread as in /portal/messages, read and written through the same
// pieces; only the frame differs. Wide pages dock it beside the work without taking focus away;
// narrow pages open it as a full-width drawer.
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
  triggerLabel: string;
  toggle: () => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
};

const ContextualMessagesContext = createContext<ContextualMessagesValue | null>(null);

/** Everything a target supplies to the shared shell. Only the wrapper knows its backend context. */
type ContextualTarget = {
  composerTarget: string;
  counterpartName: string;
  contextThread: GuidanceThreadResponse | null;
  contextUpdatedAt: number;
  threadId: string | null;
  canStart: boolean;
  available: boolean;
  accessEnded: boolean;
  /** The narrow capability for this kind; the composer and status control use it. */
  canWrite: boolean;
  canManageDirect: boolean;
  send: (intent: SendIntent) => Promise<{ data: GuidanceOpenResponse }>;
  sendErrorContext: GuidanceSendContext;
  reconcileContext: (threadId: string | null) => Promise<unknown>;
  hintScope: (changed: string) => MessagesRefreshScope | null;
  access: GuidanceMessagesAccess;
  viewer: GuidanceViewer;
  currentUserId: string;
  panelTitle: string;
  triggerLabel: string;
  subtitle: (thread: GuidanceThreadResponse | null, counterpartName: string) => ReactNode;
  emptyMessage: string;
  endedMessage: string | null;
};

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
    <AppointmentContextualHost
      key={user.id}
      appointmentId={appointmentId}
      counterpartName={counterpartName}
      enabled={enabled}
      access={getGuidanceMessagesAccess(user)}
      currentUserId={user.id}
    >
      {children}
    </AppointmentContextualHost>
  );
}

function AppointmentContextualHost({
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
  const latestPinRef = useRef<number | null>(null);
  const { query, threadId, contextThread, canStart, available } = useAppointmentMessagesContext(
    appointmentId,
    enabled && access.hasWorkspace,
  );
  const { mutateAsync } = useSendAppointmentMessage(appointmentId, threadId, latestPinRef);
  return (
    <ContextualHost
      latestPinRef={latestPinRef}
      target={{
        composerTarget: `appointment:${appointmentId}`,
        counterpartName,
        contextThread,
        contextUpdatedAt: query.dataUpdatedAt,
        threadId,
        canStart,
        available,
        accessEnded: false,
        canWrite: access.canWrite,
        canManageDirect: access.canManageDirect,
        send: mutateAsync,
        sendErrorContext: "thread",
        reconcileContext: (id) => reconcileAppointmentMessages(queryClient, appointmentId, id),
        hintScope: (changed) => contextualHintScope(threadId, changed),
        access,
        viewer: access.viewer,
        currentUserId,
        panelTitle: "Messages",
        triggerLabel: "Messages",
        subtitle: (thread, name) => `${thread ? threadTitle(thread, access.viewer) : name} · Counseling`,
        emptyMessage: "No conversation has started for this counseling appointment yet.",
        endedMessage: null,
      }}
    >
      {children}
    </ContextualHost>
  );
}

/**
 * Wraps the coverage page of one Counseling grant. The trigger renders only when the live
 * predicate offers a conversation (existing or startable); an ended grant the reader already had
 * open keeps the panel to show the ended copy instead of dropping it silently.
 */
export function GuidanceCaseCoordinationMessages({
  grantId,
  enabled,
  children,
}: {
  grantId: string;
  enabled: boolean;
  children: ReactNode;
}) {
  const { user } = usePortalSession();
  return (
    <CaseCoordinationContextualHost
      key={user.id}
      grantId={grantId}
      enabled={enabled}
      access={getGuidanceMessagesAccess(user)}
      currentUserId={user.id}
    >
      {children}
    </CaseCoordinationContextualHost>
  );
}

function CaseCoordinationContextualHost({
  grantId,
  enabled,
  access,
  currentUserId,
  children,
}: {
  grantId: string;
  enabled: boolean;
  access: GuidanceMessagesAccess;
  currentUserId: string;
  children: ReactNode;
}) {
  const queryClient = useQueryClient();
  const latestPinRef = useRef<number | null>(null);
  const { query, threadId, contextThread, counterpart, canStart, available, accessEnded } =
    useCaseCoordinationMessagesContext(grantId, enabled && access.canViewCaseCoordination);
  const { mutateAsync } = useSendCaseCoordinationMessage(grantId, threadId, latestPinRef);
  const counterpartName = counterpart ? personName(counterpart, "Counselor") : "Counselor";
  return (
    <ContextualHost
      latestPinRef={latestPinRef}
      target={{
        composerTarget: `case-grant:${grantId}`,
        counterpartName,
        contextThread,
        contextUpdatedAt: query.dataUpdatedAt,
        threadId,
        canStart,
        available,
        accessEnded,
        canWrite: access.canManageCaseCoordination,
        canManageDirect: false,
        send: mutateAsync,
        sendErrorContext: "case-coordination",
        reconcileContext: (id) => reconcileCaseCoordinationMessages(queryClient, grantId, id),
        hintScope: (changed) => contextualHintScope(threadId, changed),
        access,
        viewer: access.viewer,
        currentUserId,
        panelTitle: "Case coordination",
        triggerLabel: "Coordinate with Counselor",
        subtitle: (thread, name) => (
          <span className="break-words">
            {name}
            {thread?.student_subject
              ? ` · ${personName(thread.student_subject, "Student")}`
              : " · Case coordination"}
          </span>
        ),
        emptyMessage: CASE_COORDINATION_ENTRY_COPY,
        endedMessage: CASE_COORDINATION_ENDED_COPY,
      }}
    >
      {children}
    </ContextualHost>
  );
}

function ContextualHost({
  target,
  latestPinRef,
  children,
}: {
  target: ContextualTarget;
  latestPinRef: RefObject<number | null>;
  children: ReactNode;
}) {
  const layoutRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const [requestedOpen, setRequestedOpen] = useState(false);
  const docked = useDocked(layoutRef);
  // An ended grant closes the trigger for good but keeps an already-open panel to show the ended
  // copy; a context that no longer offers anything never opens.
  const open = requestedOpen && (target.available || target.accessEnded);

  // The panel keeps the thread detail fresh; this only reads it, never fetches it.
  const detail = useGuidanceMessagesGetThread(target.threadId ?? "", { query: { enabled: false } });
  const thread: GuidanceThreadResponse | null =
    detail.data && detail.dataUpdatedAt >= target.contextUpdatedAt
      ? detail.data.data
      : target.contextThread ?? detail.data?.data ?? null;
  const canSend =
    target.canWrite &&
    !target.accessEnded &&
    (thread ? thread.status === "OPEN" : target.canStart);

  const composer = useMessageComposer({
    target: target.composerTarget,
    send: target.send,
    describeError: (error) => describeSendError(error, target.sendErrorContext),
    blocked: !canSend,
  });

  // While closed, keep the unread count beside the trigger current from hints for this thread only.
  // Nothing is polled and no history is read until the panel opens.
  useRealtimeEvent("messages.thread_changed", (event) => {
    if (open || !target.threadId || changedThreadId(event) !== target.threadId) return;
    void target.reconcileContext(null);
  });

  const close = useCallback(() => {
    setRequestedOpen(false);
  }, []);
  const toggle = useCallback(() => setRequestedOpen((current) => !current), []);

  const value: ContextualMessagesValue = {
    available: target.available,
    open,
    unread: thread?.unread_count ?? 0,
    panelId,
    triggerLabel: target.triggerLabel,
    toggle,
    triggerRef,
  };
  const panel = (mode: "docked" | "drawer") => (
    <ContextualPanel
      mode={mode}
      target={target}
      thread={thread}
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
  triggerLabel,
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
      label={unreadText ? `${triggerLabel} ${unreadText}` : triggerLabel}
      className={className}
      aria-expanded={open}
      aria-controls={open ? panelId : undefined}
      onClick={toggle}
    />
  );
}

function ContextualPanel({
  mode,
  target,
  thread,
  composer,
  latestPinRef,
  onClose,
}: {
  mode: "docked" | "drawer";
  target: ContextualTarget;
  thread: GuidanceThreadResponse | null;
  composer: MessageComposerController;
  latestPinRef: RefObject<number | null>;
  onClose: () => void;
}) {
  const headingId = `${useContext(ContextualMessagesContext)?.panelId ?? "messages"}-heading`;
  const [status, setStatus] = useState("");
  const state = useThreadConversation({
    threadId: target.threadId,
    active: true,
    canWrite: target.canWrite && !target.accessEnded,
    canManageDirect: target.canManageDirect,
    latestPinRef,
  });
  const shown = state.thread ?? thread;
  const resolved = shown?.status === "RESOLVED";
  const ended = target.accessEnded;

  // While open: the context always (another tab may have started the thread), and the thread itself
  // when it exists. Hints for other threads are ignored once this thread is known.
  useMessagesFreshness({
    reconcile: () => target.reconcileContext(target.threadId),
    hintScope: (changed) => target.hintScope(changed),
  });

  // A thread that became unavailable sends the panel back to the backend's current answer, which
  // closes the panel when Messages is no longer offered here, or shows the ended copy for a case.
  const concealed = Boolean(target.threadId) && state.concealed;
  const reconcileRef = useRef(target.reconcileContext);
  useEffect(() => {
    reconcileRef.current = target.reconcileContext;
  });
  useEffect(() => {
    if (concealed) void reconcileRef.current(null);
  }, [concealed]);

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
            {target.panelTitle}
          </Heading>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
            {target.subtitle(shown ?? null, target.counterpartName)}
            {resolved && !ended ? <ResolvedBadge /> : null}
          </p>
        </div>
        <div className="flex shrink-0 items-start gap-1">
          {shown && !ended && target.viewer === "staff" && target.canWrite ? (
            <ThreadStatusControl thread={shown} viewer={target.viewer} compact onChanged={setStatus} />
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
      {ended ? (
        <p role="status" className="px-4 py-4 text-sm text-muted">{target.endedMessage}</p>
      ) : target.threadId ? (
        concealed ? (
          <p className="px-4 py-4 text-sm text-muted">This conversation is no longer available to your account.</p>
        ) : (
          <ConversationHistoryRegion state={state} currentUserId={target.currentUserId} />
        )
      ) : (
        // No thread exists until the first Message is confirmed; nothing here pretends otherwise.
        <div className="flex min-h-0 flex-1 items-end px-4 py-4">
          <p className="text-sm text-muted">{target.emptyMessage}</p>
        </div>
      )}
      {ended ? null : !target.canWrite ? (
        <ComposerNote>You can read this conversation, but your account cannot send messages.</ComposerNote>
      ) : (
        <MessageComposerView
          controller={composer}
          label={`Message to ${target.counterpartName}`}
          unavailable={resolved && shown ? <ResolvedNote thread={shown} viewer={target.viewer} /> : null}
          templates={messageTemplatesFor(target.access)}
          className="sm:px-3"
        />
      )}
      {target.threadId && !concealed && !ended ? (
        <div className="border-t border-border bg-surface px-4 py-2">
          <GuardedPortalLink
            href={`/portal/messages/${target.threadId}`}
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
