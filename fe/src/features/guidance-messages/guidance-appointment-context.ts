"use client";

import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";

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
import { errorStatus, isConcealingError, isThreadId } from "@/features/guidance-messages/guidance-messages-shared";
import type { SendIntent } from "@/features/guidance-messages/guidance-message-send";
import {
  getGuidanceMessagesGetAppointmentContextQueryKey,
  guidanceMessagesOpenCounselingThread,
  useGuidanceMessagesGetAppointmentContext,
  type guidanceMessagesGetAppointmentContextResponseSuccess,
} from "@/lib/api/generated/guidance-messages/guidance-messages";
import type { GuidanceOpenResponse } from "@/lib/api/generated/model";

// A contextual surface knows an Appointment, not a thread. The backend resolves the Appointment's
// one Counseling thread (ADR-103): an existing thread for its persisted participants, or whether
// this reader may start it now. The browser never scans the thread directory to find it.

export function appointmentContextQueryKey(appointmentId: string) {
  return getGuidanceMessagesGetAppointmentContextQueryKey(appointmentId);
}

/**
 * The Appointment's Messages context. A concealed or unreadable context offers nothing; a transient
 * refresh failure keeps the last confirmed context so an open panel is not dropped by one failure.
 */
export function useAppointmentMessagesContext(appointmentId: string, enabled: boolean) {
  const query = useGuidanceMessagesGetAppointmentContext(appointmentId, {
    query: { enabled: enabled && isThreadId(appointmentId) },
  });
  const usable = !isConcealingError(query.error) && (!query.isError || canShowLastKnownData(query));
  const context = usable ? query.data?.data : undefined;
  return {
    query,
    threadId: context?.thread?.id ?? null,
    contextThread: context?.thread ?? null,
    canStart: context?.can_start ?? false,
    available: Boolean(context && (context.thread || context.can_start)),
  };
}

/**
 * Which hints an open contextual panel acts on. Before a thread exists, any hint for this reader may
 * mean another tab started it, so the context is asked again; afterwards only this thread's hints.
 */
export function contextualHintScope(threadId: string | null, changed: string): { activeThread: true } | null {
  return !threadId || changed === threadId ? { activeThread: true } : null;
}

/** Re-reads the context and, once one exists, the thread and its newest page. */
export function reconcileAppointmentMessages(
  queryClient: Pick<QueryClient, "invalidateQueries">,
  appointmentId: string,
  threadId: string | null,
) {
  return Promise.allSettled([
    queryClient.invalidateQueries({ queryKey: appointmentContextQueryKey(appointmentId), exact: true }),
    ...(threadId
      ? [
          queryClient.invalidateQueries({ queryKey: guidanceThreadQueryKey(threadId), exact: true }),
          queryClient.invalidateQueries({ queryKey: guidanceConversationQueryKey(threadId), exact: true }),
        ]
      : []),
  ]);
}

/** Records a confirmed open-or-send: the thread, its Message and the Appointment's context. */
export function cacheOpenedCounselingThread(queryClient: QueryClient, appointmentId: string, opened: GuidanceOpenResponse) {
  const { thread, message } = opened;
  void invalidateGuidanceWork(queryClient);
  cacheThread(queryClient, thread);
  queryClient.setQueryData<ConversationHistory>(guidanceConversationQueryKey(thread.id), (current) =>
    current
      ? appendConfirmedMessage(current, message)
      : message.sequence === 1
        ? { messages: [message], hasOlder: false }
        : current,
  );
  queryClient.setQueryData<guidanceMessagesGetAppointmentContextResponseSuccess>(
    appointmentContextQueryKey(appointmentId),
    (current) => (current ? { ...current, data: { thread, can_start: false } } : current),
  );
}

/**
 * Every contextual send goes through the Appointment's canonical open endpoint. The first Message
 * creates the thread in the same transaction; later ones join the same thread, and a retry of an
 * unconfirmed first Message stays valid after the thread appears, because the target never changes.
 */
export function useSendAppointmentMessage(
  appointmentId: string,
  threadId: string | null,
  latestPinRef: RefObject<number | null>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (intent: SendIntent) =>
      guidanceMessagesOpenCounselingThread(appointmentId, {
        client_message_id: intent.clientMessageId,
        body: intent.body,
      }),
    onSuccess: (response) => {
      latestPinRef.current = response.data.message.sequence;
      cacheOpenedCounselingThread(queryClient, appointmentId, response.data);
      void reconcileGuidanceMessages(queryClient, response.data.thread.id, { activeThread: true });
    },
    onError: (error) => {
      // A changed relationship, a resolved thread or lost access: read the context again so the panel
      // shows what is true now. The draft stays in the composer.
      if (isConcealingError(error) || errorStatus(error) === 409) {
        void reconcileAppointmentMessages(queryClient, appointmentId, threadId);
      }
    },
  });
}
