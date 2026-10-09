"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useSyncExternalStore, type RefObject } from "react";

import {
  appendConfirmedMessage,
  cacheConfirmedRead,
  guidanceConversationQueryKey,
  guidanceDirectoryQueryFamily,
  guidanceThreadQueryKey,
  HISTORY_PAGE_SIZE,
  mergeNewestPage,
  mergeOlderPage,
  type ConversationHistory,
} from "@/features/guidance-messages/guidance-messages-cache";
import { reconcileGuidanceMessages } from "@/features/guidance-messages/guidance-messages-freshness";
import { errorStatus, isConcealingError } from "@/features/guidance-messages/guidance-messages-shared";
import type { SendIntent } from "@/features/guidance-messages/guidance-message-send";
import {
  guidanceMessagesListMessages,
  guidanceMessagesMarkRead,
  guidanceMessagesSendMessage,
  type guidanceMessagesGetThreadResponseSuccess,
} from "@/lib/api/generated/guidance-messages/guidance-messages";
import type { GuidanceThreadResponse } from "@/lib/api/generated/model";

/**
 * The open conversation's history: a refresh reads only the newest page and joins it to what is
 * loaded (guidance-messages-cache.ts). Older pages are read on request and joined through a
 * mutation, so a response that arrives after the signed-in account changed is refused by the
 * shared account ownership boundary instead of reaching the cache.
 */
export function useConversationHistory(threadId: string, enabled: boolean) {
  const queryClient = useQueryClient();
  const queryKey = guidanceConversationQueryKey(threadId);
  const history = useQuery({
    queryKey,
    enabled,
    queryFn: async ({ signal }) => {
      const response = await guidanceMessagesListMessages(threadId, { page_size: HISTORY_PAGE_SIZE }, { signal });
      return mergeNewestPage(queryClient.getQueryData<ConversationHistory>(queryKey), response.data);
    },
  });
  const older = useMutation({
    mutationFn: async (anchor: number) =>
      (await guidanceMessagesListMessages(threadId, { before_sequence: anchor, page_size: HISTORY_PAGE_SIZE })).data,
    onSuccess: (page, anchor) => {
      queryClient.setQueryData<ConversationHistory>(queryKey, (current) => mergeOlderPage(current, page, anchor));
    },
  });
  return { history, older };
}

/** `latestPinRef` keeps the history at its end until the sent Message is on screen. */
export function useSendThreadMessage(threadId: string, latestPinRef: RefObject<number | null>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (intent: SendIntent) =>
      guidanceMessagesSendMessage(threadId, { client_message_id: intent.clientMessageId, body: intent.body }),
    onSuccess: (response) => {
      latestPinRef.current = response.data.sequence;
      queryClient.setQueryData<ConversationHistory>(guidanceConversationQueryKey(threadId), (current) =>
        appendConfirmedMessage(current, response.data),
      );
      void reconcileGuidanceMessages(queryClient, threadId, { activeThread: true });
    },
    onError: (error) => {
      // A conflict usually means the thread was resolved; concealment means access was lost.
      // Either way the thread is read again so what is shown matches the backend.
      if (isConcealingError(error) || errorStatus(error) === 409) {
        void queryClient.invalidateQueries({ queryKey: guidanceThreadQueryKey(threadId), exact: true });
      }
    },
  });
}

export function cacheThread(
  queryClient: ReturnType<typeof useQueryClient>,
  thread: GuidanceThreadResponse,
) {
  queryClient.setQueryData<guidanceMessagesGetThreadResponseSuccess>(guidanceThreadQueryKey(thread.id), (current) =>
    current ? { ...current, data: thread } : { data: thread, status: 200, headers: {} },
  );
}

const subscribeVisibility = (onChange: () => void) => {
  document.addEventListener("visibilitychange", onChange);
  return () => document.removeEventListener("visibilitychange", onChange);
};
const documentVisible = () => document.visibilityState === "visible";
const serverDocumentVisible = () => false;

export function useDocumentVisible(): boolean {
  return useSyncExternalStore(subscribeVisibility, documentVisible, serverDocumentVisible);
}

/**
 * Advances this reader's private read cursor, never anyone else's. It moves only while the
 * conversation is open in a visible tab, its newest loaded Message is in view, and the cursor is
 * behind it; one request per newer sequence. Directory loads, hidden tabs and prefetches never mark
 * anything read, and nothing here tells the other participant.
 */
export function useMarkThreadRead({
  threadId,
  thread,
  threadUpdatedAt,
  latestSequence,
  atLatest,
  enabled,
}: {
  threadId: string;
  thread: GuidanceThreadResponse | undefined;
  threadUpdatedAt: number;
  latestSequence: number;
  atLatest: boolean;
  enabled: boolean;
}) {
  const queryClient = useQueryClient();
  const visible = useDocumentVisible();
  const requested = useRef(0);
  const markRead = useMutation({
    mutationFn: (sequence: number) => guidanceMessagesMarkRead(threadId, { sequence }),
    onSuccess: (response) => {
      cacheConfirmedRead(queryClient, threadId, response.data.own_last_read_sequence);
      void queryClient.invalidateQueries({ queryKey: guidanceDirectoryQueryFamily() });
    },
    onError: (error) => {
      // The next confirmed refresh of the thread may try again; concealment closes the thread.
      requested.current = 0;
      if (isConcealingError(error)) {
        void queryClient.invalidateQueries({ queryKey: guidanceThreadQueryKey(threadId), exact: true });
      }
    },
  });
  const { mutate } = markRead;
  const ownRead = thread?.own_last_read_sequence ?? 0;

  useEffect(() => {
    if (!enabled || !thread || !visible || !atLatest || latestSequence === 0) return;
    if (latestSequence <= ownRead || latestSequence <= requested.current) return;
    requested.current = latestSequence;
    mutate(latestSequence);
  }, [atLatest, enabled, latestSequence, mutate, ownRead, thread, threadUpdatedAt, visible]);
}
