"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { PanelMessage } from "@/components/ui/panel";
import { canShowLastKnownData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import {
  cacheThread,
  useConversationHistory,
  useMarkThreadRead,
  useSendThreadMessage,
} from "@/features/guidance-messages/guidance-conversation-data";
import { GuidanceMessageComposer } from "@/features/guidance-messages/guidance-message-composer";
import { GuidanceMessageList } from "@/features/guidance-messages/guidance-message-list";
import { guidanceDirectoryQueryFamily } from "@/features/guidance-messages/guidance-messages-cache";
import {
  describeOlderError,
  describeSendError,
  describeStatusChangeError,
} from "@/features/guidance-messages/guidance-messages-errors";
import {
  personName,
  threadRoutingFacts,
  threadStatusLabel,
  threadSubtitle,
  threadTitle,
  type GuidanceViewer,
} from "@/features/guidance-messages/guidance-messages-presentation";
import {
  CONVERSATION_HEADING_ID,
  ConversationSkeleton,
  isConcealingError,
  isContentUnavailable,
  isThreadId,
} from "@/features/guidance-messages/guidance-messages-shared";
import { useGuidanceWorkspace } from "@/features/guidance-messages/guidance-messages-workspace";
import {
  guidanceMessagesReopenThread,
  guidanceMessagesResolveThread,
  useGuidanceMessagesGetThread,
} from "@/lib/api/generated/guidance-messages/guidance-messages";
import type { GuidanceThreadResponse } from "@/lib/api/generated/model";
import { focusHeading } from "@/lib/focus-heading";
import { cn } from "@/lib/utils/cn";

const STUDENT_OFFICE_CONTEXT = "Guidance and Counseling Office";

/** One conversation: who it is with, its Messages in order, and the composer. */
export function GuidanceConversation({ threadId }: { threadId: string }) {
  const workspace = useGuidanceWorkspace();
  const { access, viewer, currentUserId } = workspace;
  const valid = isThreadId(threadId);
  const threadQuery = useGuidanceMessagesGetThread(threadId, { query: { enabled: valid } });
  const { history, older } = useConversationHistory(threadId, valid);
  const latestPinRef = useRef<number | null>(null);
  const send = useSendThreadMessage(threadId, latestPinRef);
  const [atLatest, setAtLatest] = useState(true);

  // On a narrow screen the conversation replaced the directory, so focus moves to its heading. Side
  // by side, focus stays on the conversation the reader chose.
  const focusOnOpen = useRef(workspace.moves > 0);
  useEffect(() => {
    if (!focusOnOpen.current) return;
    focusOnOpen.current = false;
    if (!workspace.isSplit()) focusHeading(CONVERSATION_HEADING_ID);
  }, [workspace]);

  // Access loss, concealment and a signed-out session close the conversation; only a transient
  // failure may keep the last confirmed details on screen.
  const concealed = !valid || isConcealingError(threadQuery.error) || isConcealingError(history.error);
  const thread = !concealed && (!threadQuery.isError || canShowLastKnownData(threadQuery))
    ? threadQuery.data?.data
    : undefined;
  const conversation = !concealed && (!history.isError || canShowLastKnownData(history)) ? history.data : undefined;
  const latestSequence = conversation?.messages.at(-1)?.sequence ?? 0;

  useMarkThreadRead({
    threadId,
    thread,
    threadUpdatedAt: threadQuery.dataUpdatedAt,
    latestSequence,
    atLatest,
    enabled: access.canWrite && !concealed && conversation !== undefined,
  });

  const loadOlder = useCallback((anchor: number) => older.mutate(anchor), [older]);
  const sendIntent = useCallback(
    (intent: Parameters<typeof send.mutateAsync>[0]) => send.mutateAsync(intent),
    [send],
  );
  const describe = useCallback((error: unknown) => describeSendError(error, "thread"), []);

  if (concealed) {
    return (
      <ConversationFrame title="Conversation unavailable">
        <PanelMessage
          action={
            <GuardedPortalLink href="/portal/messages" className={buttonVariants({ variant: "secondary" })}>
              Back to Messages
            </GuardedPortalLink>
          }
        >
          This conversation does not exist, or your account no longer has access to it.
        </PanelMessage>
      </ConversationFrame>
    );
  }

  if (!thread) {
    const failed = threadQuery.isError;
    return (
      <ConversationFrame title={failed ? "Conversation not loaded" : "Loading conversation…"}>
        {failed ? (
          <PanelMessage
            role="alert"
            tone="danger"
            action={
              <Button variant="secondary" disabled={threadQuery.isFetching} onClick={() => void threadQuery.refetch()}>
                {threadQuery.isFetching ? "Retrying…" : "Retry"}
              </Button>
            }
          >
            This conversation could not be loaded.
          </PanelMessage>
        ) : (
          <ConversationSkeleton />
        )}
      </ConversationFrame>
    );
  }

  const resolved = thread.status === "RESOLVED";
  const staffCanChangeStatus = viewer === "staff" && access.canManageStaff;

  let historyRegion: ReactNode;
  if (conversation) {
    historyRegion = (
      <GuidanceMessageList
        threadId={threadId}
        messages={conversation.messages}
        hasOlder={conversation.hasOlder}
        currentUserId={currentUserId}
        loadingOlder={older.isPending}
        olderError={older.isError ? describeOlderError(older.error) : null}
        onLoadOlder={loadOlder}
        onAtLatestChange={setAtLatest}
        latestPinRef={latestPinRef}
      />
    );
  } else if (history.isError) {
    historyRegion = (
      <div className="min-h-0 flex-1 overflow-y-auto">
        <PanelMessage
          role="alert"
          tone="danger"
          action={
            <Button variant="secondary" disabled={history.isFetching} onClick={() => void history.refetch()}>
              {history.isFetching ? "Retrying…" : "Retry"}
            </Button>
          }
        >
          {isContentUnavailable(history.error)
            ? "Messages in this conversation cannot be shown right now because confidential message content is temporarily unavailable."
            : "Messages could not be loaded."}
        </PanelMessage>
      </div>
    );
  } else {
    historyRegion = (
      <div className="min-h-0 flex-1 overflow-hidden">
        <ConversationSkeleton />
      </div>
    );
  }

  return (
    <ConversationFrame
      title={threadTitle(thread, viewer)}
      details={<ThreadDetails thread={thread} viewer={viewer} currentUserId={currentUserId} />}
      actions={staffCanChangeStatus ? <ThreadStatusControl thread={thread} /> : null}
    >
      {history.isError && conversation ? (
        <div className="px-3 sm:px-4">
          <RefreshFailureNotice
            message={
              isContentUnavailable(history.error)
                ? "New messages cannot be shown right now because confidential message content is temporarily unavailable. Showing the messages already loaded."
                : "Messages could not be refreshed. Showing the messages already loaded."
            }
            retrying={history.isFetching}
            onRetry={() => void history.refetch()}
          />
        </div>
      ) : threadQuery.isError ? (
        <div className="px-3 sm:px-4">
          <RefreshFailureNotice retrying={threadQuery.isFetching} onRetry={() => void threadQuery.refetch()} />
        </div>
      ) : null}
      {historyRegion}
      {!access.canWrite ? (
        <ComposerNote>You can read this conversation, but your account cannot send messages.</ComposerNote>
      ) : (
        // Stays mounted when the conversation is resolved, so an unsent draft is kept (read-only).
        <GuidanceMessageComposer
          target={`thread:${threadId}`}
          label={`Message to ${threadTitle(thread, viewer)}`}
          send={sendIntent}
          describeError={describe}
          unavailable={resolved ? <ResolvedNote thread={thread} viewer={viewer} /> : null}
        />
      )}
    </ConversationFrame>
  );
}

function ResolvedNote({ thread, viewer }: { thread: GuidanceThreadResponse; viewer: GuidanceViewer }) {
  return (
    <p>
      <span className="font-semibold text-ink">This conversation is resolved.</span>{" "}
      {viewer === "student" && thread.kind === "OFFICE" ? (
        <>
          To contact the Guidance Office again,{" "}
          <GuardedPortalLink href="/portal/messages/new" className="font-semibold text-brand underline underline-offset-4">
            start a new message
          </GuardedPortalLink>
          .
        </>
      ) : viewer === "staff" ? (
        "Reopen it to send more messages."
      ) : null}
    </p>
  );
}

function ComposerNote({ children }: { children: ReactNode }) {
  return (
    <div className="border-t border-brand-line bg-surface px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] text-sm text-muted">
      {children}
    </div>
  );
}

/**
 * The conversation pane's frame. Its heading stays the same element while the conversation loads,
 * fails or arrives, so focus placed on it is never lost to a re-render.
 */
export function ConversationFrame({
  title,
  details,
  actions,
  children,
}: {
  title: string;
  details?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="border-b border-brand-line px-4 py-3">
        <GuardedPortalLink
          href="/portal/messages"
          aria-label="Back to Messages"
          className={cn(pageBackLinkClass, "mb-1 gap-1.5 @[42rem]/messages:hidden")}
        >
          <ArrowLeft size={16} aria-hidden="true" />
          Messages
        </GuardedPortalLink>
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="min-w-0">
            <h2
              id={CONVERSATION_HEADING_ID}
              tabIndex={-1}
              className="break-words font-heading text-lg font-semibold leading-snug text-ink focus:outline-none"
            >
              {title}
            </h2>
            {details}
          </div>
          {actions}
        </div>
      </header>
      {children}
    </div>
  );
}

function ThreadDetails({
  thread,
  viewer,
  currentUserId,
}: {
  thread: GuidanceThreadResponse;
  viewer: GuidanceViewer;
  currentUserId: string;
}) {
  const subtitle = viewer === "student" && thread.kind === "OFFICE" ? STUDENT_OFFICE_CONTEXT : threadSubtitle(thread, viewer);
  const { college, assignedTo } = threadRoutingFacts(thread, viewer);
  const resolved = thread.status === "RESOLVED";
  return (
    <div className="mt-0.5 space-y-0.5 text-sm text-muted">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="break-words">{[subtitle, college].filter(Boolean).join(" · ")}</span>
        {resolved ? (
          <span className="inline-flex rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs font-semibold text-muted">
            {threadStatusLabel(thread.status)}
          </span>
        ) : null}
      </p>
      {assignedTo ? (
        <p className="break-words text-xs">
          {thread.assigned_to?.id === currentUserId ? "Assigned to you" : `Assigned to ${assignedTo}`}
        </p>
      ) : null}
    </div>
  );
}

/**
 * Resolve and Reopen for Guidance staff. One button changes between the two, so focus stays put
 * after either. Resolving asks first; reopening is direct. The backend still decides both.
 */
function ThreadStatusControl({ thread }: { thread: GuidanceThreadResponse }) {
  const queryClient = useQueryClient();
  const { showStatus } = useGuidanceWorkspace();
  const [confirming, setConfirming] = useState(false);
  const [reopenError, setReopenError] = useState<string | null>(null);
  const settle = (response: { data: GuidanceThreadResponse }) => {
    cacheThread(queryClient, response.data);
    void queryClient.invalidateQueries({ queryKey: guidanceDirectoryQueryFamily() });
  };
  const resolve = useMutation({
    mutationFn: () => guidanceMessagesResolveThread(thread.id),
    onSuccess: settle,
  });
  const reopen = useMutation({
    mutationFn: () => guidanceMessagesReopenThread(thread.id),
    onSuccess: settle,
  });
  const resolved = thread.status === "RESOLVED";
  const student = personName(thread.student, "The Student");

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        variant="secondary"
        className="min-h-10"
        disabled={reopen.isPending}
        onClick={() => {
          if (!resolved) {
            resolve.reset();
            setConfirming(true);
            return;
          }
          setReopenError(null);
          reopen.mutate(undefined, {
            onSuccess: () => showStatus("Conversation reopened."),
            onError: (error) => setReopenError(describeStatusChangeError(error, "reopen")),
          });
        }}
      >
        {resolved ? (reopen.isPending ? "Reopening…" : "Reopen conversation") : "Resolve conversation"}
      </Button>
      {reopenError && resolved ? (
        <p role="alert" className="max-w-xs text-right text-sm text-danger">
          {reopenError}
        </p>
      ) : null}
      <ConsequentialActionDialog
        open={confirming}
        title="Resolve this conversation?"
        confirmLabel="Resolve conversation"
        pendingLabel="Resolving…"
        pending={resolve.isPending}
        error={resolve.isError ? describeStatusChangeError(resolve.error, "resolve") : null}
        onOpenChange={setConfirming}
        onConfirm={() =>
          resolve.mutate(undefined, {
            onSuccess: () => {
              setConfirming(false);
              showStatus("Conversation resolved.");
            },
          })
        }
      >
        <p>
          {student} will not be able to send messages here until the conversation is reopened. Its
          messages stay readable.
        </p>
        {thread.kind === "OFFICE" ? (
          <p>If they write to the Guidance Office again, a new conversation starts.</p>
        ) : null}
      </ConsequentialActionDialog>
    </div>
  );
}
