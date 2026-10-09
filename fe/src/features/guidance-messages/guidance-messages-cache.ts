import type { InfiniteData, QueryClient } from "@tanstack/react-query";

import {
  getGuidanceMessagesGetThreadQueryKey,
  getGuidanceMessagesListMessagesQueryKey,
  getGuidanceMessagesListThreadsQueryKey,
  type guidanceMessagesListThreadsResponseSuccess,
} from "@/lib/api/generated/guidance-messages/guidance-messages";
import type {
  GuidanceMessagePage,
  GuidanceMessageResponse,
  GuidanceThreadResponse,
} from "@/lib/api/generated/model";

// Guidance Messages server state lives only in the in-memory QueryClient, so the account ownership
// boundary (lib/query/account-ownership.ts) discards it with the rest of an account's records.
// Nothing here is persisted, and no Message body is ever read from a realtime hint.

export const DIRECTORY_PAGE_SIZE = 20;
/** The backend's largest history page (ADR-102). */
export const HISTORY_PAGE_SIZE = 50;

export function guidanceDirectoryQueryKey() {
  return [...getGuidanceMessagesListThreadsQueryKey({ page_size: DIRECTORY_PAGE_SIZE }), "directory"] as const;
}

/** Every directory query, whatever its pages. */
export function guidanceDirectoryQueryFamily() {
  return getGuidanceMessagesListThreadsQueryKey();
}

export function guidanceThreadQueryKey(threadId: string) {
  return getGuidanceMessagesGetThreadQueryKey(threadId);
}

export function guidanceConversationQueryKey(threadId: string) {
  return [...getGuidanceMessagesListMessagesQueryKey(threadId), "conversation"] as const;
}

export type DirectoryData = InfiniteData<guidanceMessagesListThreadsResponseSuccess>;

/** The loaded directory rows in backend order; a row that moved between pages is shown once. */
export function directoryRows(data: DirectoryData | undefined): GuidanceThreadResponse[] {
  if (!data) return [];
  const seen = new Set<string>();
  const rows: GuidanceThreadResponse[] = [];
  for (const page of data.pages) {
    for (const thread of page.data.items) {
      if (seen.has(thread.id)) continue;
      seen.add(thread.id);
      rows.push(thread);
    }
  }
  return rows;
}

// ── Conversation history ─────────────────────────────────────────────────────────────────────
//
// One conversation keeps a contiguous, chronological run of Messages ending at the newest one the
// browser has confirmed. A refresh asks only for the newest page and joins it to what is already
// loaded, so older pages are never requested again. Messages are immutable, so a loaded Message
// never needs refreshing. When the newest page no longer reaches what is loaded (more Messages
// arrived than one page holds), the run restarts from the newest page instead of showing a gap.

export type ConversationHistory = Readonly<{
  messages: readonly GuidanceMessageResponse[];
  hasOlder: boolean;
}>;

function lastSequence(history: ConversationHistory): number {
  return history.messages.at(-1)?.sequence ?? 0;
}

export function mergeNewestPage(
  previous: ConversationHistory | undefined,
  page: GuidanceMessagePage,
): ConversationHistory {
  const newest = page.items;
  if (!previous || previous.messages.length === 0 || newest.length === 0) {
    return { messages: newest, hasOlder: page.has_older };
  }
  const first = newest[0].sequence;
  if (page.has_older && first > lastSequence(previous) + 1) {
    return { messages: newest, hasOlder: page.has_older };
  }
  const kept = previous.messages.filter((message) => message.sequence < first);
  return {
    messages: kept.length > 0 ? [...kept, ...newest] : newest,
    hasOlder: kept.length > 0 ? previous.hasOlder : page.has_older,
  };
}

/**
 * Joins a page requested with `before_sequence = anchor`. If the loaded run no longer starts at
 * that anchor (it restarted meanwhile), the page is dropped; the reader can ask again.
 */
export function mergeOlderPage(
  current: ConversationHistory | undefined,
  page: GuidanceMessagePage,
  anchor: number,
): ConversationHistory | undefined {
  if (!current || current.messages[0]?.sequence !== anchor) return current;
  const older = page.items.filter((message) => message.sequence < anchor);
  return { messages: [...older, ...current.messages], hasOlder: page.has_older };
}

/**
 * Adds the canonical Message a send returned. It joins only directly after the loaded run; when
 * other Messages came first, the newest-page refresh that follows every send brings them together.
 */
export function appendConfirmedMessage(
  current: ConversationHistory | undefined,
  message: GuidanceMessageResponse,
): ConversationHistory | undefined {
  if (!current) return current;
  const last = lastSequence(current);
  if (message.sequence <= last || (current.messages.length > 0 && message.sequence !== last + 1)) {
    return current;
  }
  return { ...current, messages: [...current.messages, message] };
}

// ── Read state ───────────────────────────────────────────────────────────────────────────────

/** Applies this reader's confirmed private cursor to cached thread rows and the open thread. */
export function cacheConfirmedRead(queryClient: QueryClient, threadId: string, sequence: number) {
  const apply = (thread: GuidanceThreadResponse): GuidanceThreadResponse => {
    if (thread.id !== threadId || sequence <= thread.own_last_read_sequence) return thread;
    // Unread counts exclude the reader's own Messages, so only a cursor at the thread's end proves
    // zero; anything else waits for the canonical refresh.
    return {
      ...thread,
      own_last_read_sequence: sequence,
      unread_count: sequence >= thread.last_sequence ? 0 : thread.unread_count,
    };
  };
  queryClient.setQueriesData<DirectoryData>({ queryKey: guidanceDirectoryQueryFamily() }, (data) =>
    data
      ? { ...data, pages: data.pages.map((page) => ({ ...page, data: { ...page.data, items: page.data.items.map(apply) } })) }
      : data,
  );
  queryClient.setQueryData<{ data: GuidanceThreadResponse }>(guidanceThreadQueryKey(threadId), (response) =>
    response ? { ...response, data: apply(response.data) } : response,
  );
}
