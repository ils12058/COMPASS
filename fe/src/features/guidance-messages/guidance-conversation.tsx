"use client";

import { ArrowLeft } from "lucide-react";
import { useCallback, useEffect, useRef, type ReactNode } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { PanelMessage } from "@/components/ui/panel";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { useSendThreadMessage } from "@/features/guidance-messages/guidance-conversation-data";
import {
  ComposerNote,
  ConversationHistoryRegion,
  ResolvedBadge,
  ResolvedNote,
  ThreadStatusControl,
  useThreadConversation,
} from "@/features/guidance-messages/guidance-conversation-surface";
import { ThreadAssignment } from "@/features/guidance-messages/guidance-handler-assignment";
import { GuidanceMessageComposer } from "@/features/guidance-messages/guidance-message-composer";
import { messageTemplatesFor } from "@/features/guidance-messages/guidance-messages-access";
import { describeSendError } from "@/features/guidance-messages/guidance-messages-errors";
import {
  threadRoutingFacts,
  threadSubtitle,
  threadTitle,
  type GuidanceViewer,
} from "@/features/guidance-messages/guidance-messages-presentation";
import { CONVERSATION_HEADING_ID, ConversationSkeleton } from "@/features/guidance-messages/guidance-messages-shared";
import { useGuidanceWorkspace } from "@/features/guidance-messages/guidance-messages-workspace";
import type { GuidanceThreadResponse } from "@/lib/api/generated/model";
import { focusHeading } from "@/lib/focus-heading";
import { cn } from "@/lib/utils/cn";

const STUDENT_OFFICE_CONTEXT = "Guidance and Counseling Office";

/** One conversation: who it is with, its Messages in order, and the composer. */
export function GuidanceConversation({ threadId }: { threadId: string }) {
  const workspace = useGuidanceWorkspace();
  const { access, viewer, currentUserId } = workspace;
  const state = useThreadConversation({ threadId, active: true, canWrite: access.canWrite });
  const send = useSendThreadMessage(threadId, state.latestPinRef);

  // On a narrow screen the conversation replaced the directory, so focus moves to its heading. Side
  // by side, focus stays on the conversation the reader chose.
  const focusOnOpen = useRef(workspace.moves > 0);
  useEffect(() => {
    if (!focusOnOpen.current) return;
    focusOnOpen.current = false;
    if (!workspace.isSplit()) focusHeading(CONVERSATION_HEADING_ID);
  }, [workspace]);

  const sendIntent = useCallback(
    (intent: Parameters<typeof send.mutateAsync>[0]) => send.mutateAsync(intent),
    [send],
  );
  const describe = useCallback((error: unknown) => describeSendError(error, "thread"), []);
  const { thread, threadQuery } = state;

  if (state.concealed) {
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

  return (
    <ConversationFrame
      title={threadTitle(thread, viewer)}
      details={
        <ThreadDetails
          thread={thread}
          viewer={viewer}
          currentUserId={currentUserId}
          // Office handler assignment is workflow ownership for staff who manage the conversation.
          canAssign={staffCanChangeStatus && thread.kind === "OFFICE"}
          onAssigned={workspace.showStatus}
        />
      }
      actions={staffCanChangeStatus ? <ThreadStatusControl thread={thread} onChanged={workspace.showStatus} /> : null}
    >
      <ConversationHistoryRegion state={state} currentUserId={currentUserId} />
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
          templates={messageTemplatesFor(access)}
        />
      )}
    </ConversationFrame>
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
  canAssign,
  onAssigned,
}: {
  thread: GuidanceThreadResponse;
  viewer: GuidanceViewer;
  currentUserId: string;
  canAssign: boolean;
  onAssigned: (text: string) => void;
}) {
  const subtitle = viewer === "student" && thread.kind === "OFFICE" ? STUDENT_OFFICE_CONTEXT : threadSubtitle(thread, viewer);
  const { college, assignedTo } = threadRoutingFacts(thread, viewer);
  const resolved = thread.status === "RESOLVED";
  return (
    <div className="mt-0.5 space-y-0.5 text-sm text-muted">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="break-words">{[subtitle, college].filter(Boolean).join(" · ")}</span>
        {resolved ? <ResolvedBadge /> : null}
      </p>
      {assignedTo || canAssign ? (
        <ThreadAssignment thread={thread} currentUserId={currentUserId} canChange={canAssign} onAssigned={onAssigned} />
      ) : null}
    </div>
  );
}
