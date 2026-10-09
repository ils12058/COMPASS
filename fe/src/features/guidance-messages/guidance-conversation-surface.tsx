"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState, type ReactNode, type RefObject } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { PanelMessage } from "@/components/ui/panel";
import { canShowLastKnownData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { cacheThread, useConversationHistory, useMarkThreadRead } from "@/features/guidance-messages/guidance-conversation-data";
import { GuidanceMessageList } from "@/features/guidance-messages/guidance-message-list";
import { guidanceDirectoryQueryFamily } from "@/features/guidance-messages/guidance-messages-cache";
import { describeOlderError, describeStatusChangeError } from "@/features/guidance-messages/guidance-messages-errors";
import { personName, type GuidanceViewer } from "@/features/guidance-messages/guidance-messages-presentation";
import {
  ConversationSkeleton,
  isConcealingError,
  isContentUnavailable,
  isThreadId,
} from "@/features/guidance-messages/guidance-messages-shared";
import {
  guidanceMessagesReopenThread,
  guidanceMessagesResolveThread,
  useGuidanceMessagesGetThread,
} from "@/lib/api/generated/guidance-messages/guidance-messages";
import type { GuidanceThreadResponse } from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";

// The pieces of one Guidance conversation that every surface shares: the full Messages workspace
// and the contextual panel on Appointment, Counseling and E-Counseling pages (ADR-103). They read
// the same canonical thread, page its history the same way and keep the same read rules; only the
// frame around them differs.

/**
 * One thread's detail and history. While `active` (the conversation is on screen), the reader's
 * private read cursor follows the newest loaded Message they can see. Access loss, concealment and a
 * signed-out session close the conversation; only a transient failure keeps the last confirmed data.
 */
export function useThreadConversation({
  threadId,
  active,
  canWrite,
  latestPinRef: providedPin,
}: {
  threadId: string | null;
  active: boolean;
  canWrite: boolean;
  /** Held by whoever sends, so the history stays at its end until the sent Message arrives. */
  latestPinRef?: RefObject<number | null>;
}) {
  const id = threadId ?? "";
  const valid = threadId !== null && isThreadId(threadId);
  const threadQuery = useGuidanceMessagesGetThread(id, { query: { enabled: valid } });
  const { history, older } = useConversationHistory(id, valid);
  const ownPin = useRef<number | null>(null);
  const latestPinRef = providedPin ?? ownPin;
  const [atLatest, setAtLatest] = useState(true);

  const concealed = !valid || isConcealingError(threadQuery.error) || isConcealingError(history.error);
  const thread = !concealed && (!threadQuery.isError || canShowLastKnownData(threadQuery))
    ? threadQuery.data?.data
    : undefined;
  const conversation = !concealed && (!history.isError || canShowLastKnownData(history)) ? history.data : undefined;

  useMarkThreadRead({
    threadId: id,
    thread,
    threadUpdatedAt: threadQuery.dataUpdatedAt,
    latestSequence: conversation?.messages.at(-1)?.sequence ?? 0,
    atLatest,
    enabled: active && canWrite && !concealed && conversation !== undefined,
  });

  const loadOlder = useCallback((anchor: number) => older.mutate(anchor), [older]);

  return { threadId: id, threadQuery, history, older, thread, conversation, concealed, latestPinRef, setAtLatest, loadOlder };
}

export type ThreadConversation = ReturnType<typeof useThreadConversation>;

/** The history region: notices for a failed refresh, then the Messages, or their loading or error state. */
export function ConversationHistoryRegion({
  state,
  currentUserId,
}: {
  state: ThreadConversation;
  currentUserId: string;
}) {
  const { history, threadQuery, conversation, older } = state;
  return (
    <>
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
      {conversation ? (
        <GuidanceMessageList
          threadId={state.threadId}
          messages={conversation.messages}
          hasOlder={conversation.hasOlder}
          currentUserId={currentUserId}
          loadingOlder={older.isPending}
          olderError={older.isError ? describeOlderError(older.error) : null}
          onLoadOlder={state.loadOlder}
          onAtLatestChange={state.setAtLatest}
          latestPinRef={state.latestPinRef}
        />
      ) : history.isError ? (
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
      ) : (
        <div className="min-h-0 flex-1 overflow-hidden">
          <ConversationSkeleton />
        </div>
      )}
    </>
  );
}

export function ResolvedNote({ thread, viewer }: { thread: GuidanceThreadResponse; viewer: GuidanceViewer }) {
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

export function ComposerNote({ children }: { children: ReactNode }) {
  return (
    <div className="border-t border-brand-line bg-surface px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] text-sm text-muted">
      {children}
    </div>
  );
}

export function ResolvedBadge() {
  return (
    <span className="inline-flex rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs font-semibold text-muted">
      Resolved
    </span>
  );
}

/**
 * Resolve and Reopen for Guidance staff. One button changes between the two, so focus stays put
 * after either. Resolving asks first; reopening is direct. The backend still decides both.
 */
export function ThreadStatusControl({
  thread,
  onChanged,
  compact = false,
}: {
  thread: GuidanceThreadResponse;
  /** Confirms a completed change, such as through the page's ActionStatus. */
  onChanged?: (text: string) => void;
  compact?: boolean;
}) {
  const queryClient = useQueryClient();
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
        className={cn("min-h-10", compact && "px-3")}
        aria-label={compact ? (resolved ? "Reopen conversation" : "Resolve conversation") : undefined}
        disabled={reopen.isPending}
        onClick={() => {
          if (!resolved) {
            resolve.reset();
            setConfirming(true);
            return;
          }
          setReopenError(null);
          reopen.mutate(undefined, {
            onSuccess: () => onChanged?.("Conversation reopened."),
            onError: (error) => setReopenError(describeStatusChangeError(error, "reopen")),
          });
        }}
      >
        {resolved
          ? reopen.isPending ? "Reopening…" : compact ? "Reopen" : "Reopen conversation"
          : compact ? "Resolve" : "Resolve conversation"}
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
              onChanged?.("Conversation resolved.");
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
