"use client";

import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import type { RefObject } from "react";

import { canShowLastKnownData } from "@/features/freshness/query-freshness";
import { cacheThread } from "@/features/guidance-messages/guidance-conversation-data";
import {
  appendConfirmedMessage,
  guidanceConversationQueryKey,
  guidanceThreadQueryKey,
  type ConversationHistory,
} from "@/features/guidance-messages/guidance-messages-cache";
import { reconcileGuidanceMessages } from "@/features/guidance-messages/guidance-messages-freshness";
import {
  isConcealingError,
  isThreadId,
} from "@/features/guidance-messages/guidance-messages-shared";
import type { SendIntent } from "@/features/guidance-messages/guidance-message-send";
import {
  getGuidanceMessagesGetCaseCoordinationContextQueryKey,
  guidanceMessagesOpenCaseCoordinationThread,
  useGuidanceMessagesGetCaseCoordinationContext,
  type guidanceMessagesGetCaseCoordinationContextResponseSuccess,
} from "@/lib/api/generated/guidance-messages/guidance-messages";
import type { GuidanceOpenResponse } from "@/lib/api/generated/model";

// A case surface knows a Counseling grant, not a thread. The server's live predicate decides
// whether the grant's one conversation exists, may be started, or has ended; the browser never
// looks it up in the thread directory.

export function caseCoordinationContextQueryKey(grantId: string) {
  return getGuidanceMessagesGetCaseCoordinationContextQueryKey(grantId);
}

/**
 * The grant's Messages context. A concealed or unreadable context offers nothing; a transient
 * refresh failure keeps the last confirmed context so an open panel is not dropped by one failure.
 */
export function useCaseCoordinationMessagesContext(grantId: string, enabled: boolean) {
  const query = useGuidanceMessagesGetCaseCoordinationContext(grantId, {
    query: { enabled: enabled && isThreadId(grantId) },
  });
  const usable = !isConcealingError(query.error) && (!query.isError || canShowLastKnownData(query));
  const context = usable ? query.data?.data : undefined;
  return {
    query,
    threadId: context?.thread?.id ?? null,
    contextThread: context?.thread ?? null,
    counterpart: context?.counterpart ?? null,
    canStart: context?.can_start ?? false,
    available: Boolean(context && (context.thread || context.can_start)),
    accessEnded: Boolean(context?.access_ended),
  };
}

/** Re-reads the context and, once one exists, the thread and its newest page. */
export function reconcileCaseCoordinationMessages(
  queryClient: Pick<QueryClient, "invalidateQueries">,
  grantId: string,
  threadId: string | null,
) {
  return Promise.allSettled([
    queryClient.invalidateQueries({
      queryKey: caseCoordinationContextQueryKey(grantId),
      exact: true,
    }),
    ...(threadId
      ? [
          queryClient.invalidateQueries({ queryKey: guidanceThreadQueryKey(threadId), exact: true }),
          queryClient.invalidateQueries({
            queryKey: guidanceConversationQueryKey(threadId),
            exact: true,
          }),
        ]
      : []),
  ]);
}

/** Records a confirmed open-or-send: the thread, its Message and the grant's context. */
export function cacheOpenedCaseCoordinationThread(
  queryClient: QueryClient,
  grantId: string,
  opened: GuidanceOpenResponse,
) {
  const { thread, message } = opened;
  cacheThread(queryClient, thread);
  queryClient.setQueryData<ConversationHistory>(guidanceConversationQueryKey(thread.id), (current) =>
    current
      ? appendConfirmedMessage(current, message)
      : message.sequence === 1
        ? { messages: [message], hasOlder: false }
        : current,
  );
  queryClient.setQueryData<guidanceMessagesGetCaseCoordinationContextResponseSuccess>(
    caseCoordinationContextQueryKey(grantId),
    (current) => (current ? { ...current, data: { ...current.data, thread, can_start: false } } : current),
  );
}

/**
 * Every case send goes through the grant's canonical open endpoint. The first Message creates the
 * thread in the same transaction and later ones join it; the live predicate is rechecked server
 * side under the grant lock, so a retry after access ends is refused rather than replayed.
 */
export function useSendCaseCoordinationMessage(
  grantId: string,
  threadId: string | null,
  latestPinRef: RefObject<number | null>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (intent: SendIntent) =>
      guidanceMessagesOpenCaseCoordinationThread(grantId, {
        client_message_id: intent.clientMessageId,
        body: intent.body,
      }),
    onSuccess: (response) => {
      latestPinRef.current = response.data.message.sequence;
      cacheOpenedCaseCoordinationThread(queryClient, grantId, response.data);
      void reconcileGuidanceMessages(queryClient, response.data.thread.id, { activeThread: true });
    },
    onError: (error) => {
      // Ended, revoked, concealed or resolved: read the context again so the panel shows what is
      // true now. The draft stays in the composer.
      if (isConcealingError(error)) {
        void reconcileCaseCoordinationMessages(queryClient, grantId, threadId);
      }
    },
  });
}
