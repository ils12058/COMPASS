"use client";

import { useInfiniteQuery } from "@tanstack/react-query";

import { Button, buttonVariants } from "@/components/ui/button";
import { PanelMessage } from "@/components/ui/panel";
import { IllustratedEmptyState } from "@/components/ui/illustrated-empty-state";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { isTransientRefreshError } from "@/features/freshness/query-freshness";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { threadActivityTime } from "@/features/guidance-messages/guidance-message-time";
import { ConversationIdentityAvatar } from "@/features/guidance-messages/guidance-conversation-identity";
import type { GuidanceMessagesAccess } from "@/features/guidance-messages/guidance-messages-access";
import {
  DIRECTORY_PAGE_SIZE,
  directoryRows,
  guidanceDirectoryQueryKey,
} from "@/features/guidance-messages/guidance-messages-cache";
import {
  threadAppointmentLabel,
  threadRoutingFacts,
  threadStartedLabel,
  threadStatusLabel,
  threadSubtitle,
  threadTitle,
  unreadLabel,
  type GuidanceViewer,
} from "@/features/guidance-messages/guidance-messages-presentation";
import { DirectorySkeleton } from "@/features/guidance-messages/guidance-messages-shared";
import { guidanceMessagesListThreads } from "@/lib/api/generated/guidance-messages/guidance-messages";
import type { GuidanceThreadResponse } from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";

// The conversation directory: who each conversation is with, its kind, last activity, the
// reader's own unread count, and whether it is resolved. It never shows Message text. Pages come in
// the backend's order (latest activity first) and grow with "Load more"; the backend has no status
// filter, so resolved conversations stay in place and are marked instead of filtered on one page.
export function GuidanceThreadDirectory({
  access,
  activeThreadId,
  currentUserId,
  canStart,
}: {
  access: GuidanceMessagesAccess;
  activeThreadId: string | null;
  currentUserId: string;
  canStart: boolean;
}) {
  const viewer = access.viewer;
  const directory = useInfiniteQuery({
    queryKey: guidanceDirectoryQueryKey(),
    queryFn: ({ pageParam, signal }) =>
      guidanceMessagesListThreads({ page: pageParam, page_size: DIRECTORY_PAGE_SIZE }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.data.has_next ? last.data.page + 1 : undefined),
    enabled: access.hasWorkspace,
  });

  // A failed refresh keeps the last confirmed rows only for a transient failure; access loss,
  // concealment, or a signed-out session clears them.
  const keepRows = directory.data !== undefined && (!directory.isError || isTransientRefreshError(directory.error));
  const rows = keepRows ? directoryRows(directory.data) : [];

  let body;
  if (directory.isPending) {
    body = <DirectorySkeleton />;
  } else if (!keepRows) {
    body = (
      <PanelMessage
        role="alert"
        tone="danger"
        action={
          <Button variant="secondary" onClick={() => void directory.refetch()} disabled={directory.isFetching}>
            {directory.isFetching ? "Retrying…" : "Retry"}
          </Button>
        }
      >
        Couldn&apos;t load the conversations. Try again.
      </PanelMessage>
    );
  } else if (rows.length === 0) {
    body = (
      <IllustratedEmptyState src={viewer === "student" && !activeThreadId && !directory.isError ? "/illustrations/guidance-messages-3d.webp" : undefined}
        action={
          canStart ? (
            <GuardedPortalLink href="/portal/messages/new" className={buttonVariants({ variant: "secondary" })}>
              New message
            </GuardedPortalLink>
          ) : undefined
        }
      >
        {viewer === "student" ? (
          <>
            <span className="block font-semibold text-ink">No messages yet.</span>
            You can write to the Guidance Office, or to your Counselor once you have a Counseling Appointment.
          </>
        ) : viewer === "faculty" ? (
          <>
            <span className="block font-semibold text-ink">No inquiries yet.</span>
            Write to the Guidance Office when you need guidance about a Student.
          </>
        ) : (
          "No Guidance conversations are available in your current workload."
        )}
      </IllustratedEmptyState>
    );
  } else {
    body = (
      <>
        <nav aria-label="Conversations">
          <ul className="divide-y divide-border">
            {rows.map((thread) => (
              <li key={thread.id}>
                <ThreadRow
                  thread={thread}
                  viewer={viewer}
                  currentUserId={currentUserId}
                  current={thread.id === activeThreadId}
                />
              </li>
            ))}
          </ul>
        </nav>
        {directory.hasNextPage ? (
          <div className="border-t border-border px-4 py-3">
            <Button
              variant="secondary"
              className="w-full"
              disabled={directory.isFetchingNextPage}
              onClick={() => void directory.fetchNextPage()}
            >
              {directory.isFetchingNextPage ? "Loading more…" : "Load more conversations"}
            </Button>
          </div>
        ) : null}
      </>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
      {directory.isError && keepRows ? (
        <div className="px-3">
          <RefreshFailureNotice
            message="Couldn't refresh the conversations. Showing the last confirmed list."
            retrying={directory.isFetching}
            onRetry={() => void directory.refetch()}
          />
        </div>
      ) : null}
      {body}
    </div>
  );
}

function ThreadRow({
  thread,
  viewer,
  currentUserId,
  current,
}: {
  thread: GuidanceThreadResponse;
  viewer: GuidanceViewer;
  currentUserId: string;
  current: boolean;
}) {
  const subtitle = threadSubtitle(thread, viewer);
  const { college, assignedTo } = threadRoutingFacts(thread, viewer);
  const unread = unreadLabel(thread.unread_count);
  const resolved = thread.status === "RESOLVED";
  const assignedLabel = assignedTo
    ? thread.assigned_to?.id === currentUserId ? "Assigned to you" : `Assigned to ${assignedTo}`
    : null;
  const time = threadActivityTime(thread.last_message_at ?? thread.created_at);
  const title = threadTitle(thread, viewer, currentUserId);
  // A Counseling conversation is told apart by its Appointment; others by when they began.
  const started = threadAppointmentLabel(thread) ?? threadStartedLabel(thread);

  return (
    <GuardedPortalLink
      href={`/portal/messages/${thread.id}`}
      data-thread-id={thread.id}
      aria-current={current ? "page" : undefined}
      className={cn(
        "block min-h-11 px-4 py-3 text-sm transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus",
        current && "bg-brand-wash ring-1 ring-inset ring-brand-line hover:bg-brand-wash",
      )}
    >
      <span className="flex items-start gap-2.5">
        <ConversationIdentityAvatar thread={thread} viewer={viewer} title={title} />
        <span className={cn("min-w-0 flex-1 [overflow-wrap:anywhere] text-ink", unread ? "font-bold" : "font-semibold")}>
          {title}
        </span>
      </span>
      <span className="mt-1 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        {subtitle || college ? (
          <span className="min-w-0 text-xs text-muted [overflow-wrap:anywhere]">
            {[subtitle, college].filter(Boolean).join(" · ")}
          </span>
        ) : null}
        {time ? (
          <time aria-label={`Last activity ${time}`} dateTime={thread.last_message_at ?? thread.created_at} className="text-xs text-muted">
            {time}
          </time>
        ) : null}
      </span>
      {started ? <span className="mt-0.5 block text-xs text-muted [overflow-wrap:anywhere]">{started}</span> : null}
      {assignedLabel ? <span className="mt-0.5 block text-xs text-muted [overflow-wrap:anywhere]">{assignedLabel}</span> : null}
      {unread || resolved ? (
        <span className="mt-1.5 flex flex-wrap gap-1.5">
          {unread ? (
            <span className="inline-flex rounded-full bg-brand px-2 py-0.5 text-xs font-semibold text-on-brand">
              {unread}
            </span>
          ) : null}
          {resolved ? (
            <span className="inline-flex rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs font-semibold text-muted">
              {threadStatusLabel(thread.status)}
            </span>
          ) : null}
        </span>
      ) : null}
    </GuardedPortalLink>
  );
}
