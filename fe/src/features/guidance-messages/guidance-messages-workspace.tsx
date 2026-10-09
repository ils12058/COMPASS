"use client";

import { SquarePen } from "lucide-react";
import { useSelectedLayoutSegment } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { ActionStatus, useActionStatus } from "@/components/ui/action-status";
import { buttonVariants } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { getGuidanceMessagesAccess, type GuidanceMessagesAccess } from "@/features/guidance-messages/guidance-messages-access";
import { useGuidanceMessagesFreshness } from "@/features/guidance-messages/guidance-messages-freshness";
import type { GuidanceViewer } from "@/features/guidance-messages/guidance-messages-presentation";
import { MESSAGES_HEADING_ID } from "@/features/guidance-messages/guidance-messages-shared";
import { GuidanceThreadDirectory } from "@/features/guidance-messages/guidance-thread-directory";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { focusHeading } from "@/lib/focus-heading";
import { cn } from "@/lib/utils/cn";

type GuidanceWorkspaceValue = {
  access: GuidanceMessagesAccess;
  viewer: GuidanceViewer;
  currentUserId: string;
  /** How many times the reader moved between the directory and a conversation in this workspace. */
  moves: number;
  /** Whether the directory and the conversation are side by side right now. */
  isSplit: () => boolean;
  showStatus: (text: string) => void;
};

const GuidanceWorkspaceContext = createContext<GuidanceWorkspaceValue | null>(null);

export function useGuidanceWorkspace(): GuidanceWorkspaceValue {
  const value = useContext(GuidanceWorkspaceContext);
  if (!value) throw new Error("useGuidanceWorkspace must be used inside GuidanceMessagesWorkspace.");
  return value;
}

/**
 * The Messages workspace, mounted by the /portal/messages layout so the directory stays in place
 * while the reader moves between conversations. Wide workspaces show the directory beside the
 * conversation; narrow ones show one at a time.
 */
export function GuidanceMessagesWorkspace({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  const access = getGuidanceMessagesAccess(user);
  if (!access.hasWorkspace) {
    return (
      <WorkspaceUnavailable title="Messages unavailable">
        Guidance Messages are not available to this account.
      </WorkspaceUnavailable>
    );
  }
  // Keyed by account: a draft, a pending send, or any other conversation state never carries over
  // to another account. Their server state leaves with the account's query cache.
  return (
    <MessagesFrame key={user.id} access={access} currentUserId={user.id}>
      {children}
    </MessagesFrame>
  );
}

function MessagesFrame({
  access,
  currentUserId,
  children,
}: {
  access: GuidanceMessagesAccess;
  currentUserId: string;
  children: ReactNode;
}) {
  // null: the directory; "new": a new message; otherwise the open thread's ID.
  const segment = useSelectedLayoutSegment();
  const activeThreadId = segment && segment !== "new" ? segment : null;
  const conversationOpen = segment !== null;
  const directory = useRef<HTMLDivElement>(null);
  const pane = useRef<HTMLDivElement>(null);
  const status = useActionStatus();
  const [route, setRoute] = useState({ segment, previous: segment, moves: 0 });
  if (route.segment !== segment) setRoute({ segment, previous: route.segment, moves: route.moves + 1 });

  useGuidanceMessagesFreshness(activeThreadId);

  const isSplit = useCallback(() => {
    const shown = (element: HTMLElement | null) => element !== null && getComputedStyle(element).display !== "none";
    return shown(directory.current) && shown(pane.current);
  }, []);

  // Returning to the directory on a narrow screen replaces the conversation, so focus goes back to
  // the conversation the reader came from, or to the directory's heading.
  useEffect(() => {
    if (route.moves === 0 || route.segment !== null || isSplit()) return;
    const row = route.previous
      ? directory.current?.querySelector<HTMLElement>(`[data-thread-id="${CSS.escape(route.previous)}"]`)
      : null;
    if (row) row.focus();
    else focusHeading(MESSAGES_HEADING_ID);
  }, [isSplit, route]);

  const canStart = access.canManageSelf || access.canManageStaff;
  const value = useMemo<GuidanceWorkspaceValue>(
    () => ({
      access,
      viewer: access.isStudent ? "student" : "staff",
      currentUserId,
      moves: route.moves,
      isSplit,
      showStatus: status.show,
    }),
    [access, currentUserId, isSplit, route.moves, status.show],
  );

  return (
    <GuidanceWorkspaceContext.Provider value={value}>
      <div className="@container/messages">
        {/* One page heading at every width: beside the directory, or for assistive technology while a
            narrow screen shows only the conversation. */}
        {conversationOpen ? <h1 className="sr-only @[42rem]/messages:hidden">Messages</h1> : null}
        <Panel
          as="div"
          className={cn(
            "grid min-h-[24rem] grid-rows-[minmax(0,1fr)] overflow-hidden @[42rem]/messages:grid-cols-[minmax(15rem,20rem)_minmax(0,1fr)]",
            // The workspace fills the screen below the top bar, so the conversation and its composer
            // stay in view while the history scrolls. A call dock keeps its own clearance.
            "h-[calc(100dvh-6rem-1px)] lg:h-[calc(100dvh-6.5rem-1px)]",
            "[:root:has([data-call-dock])_&]:h-[calc(100dvh-4.75rem-1px-var(--call-dock-clearance))]",
            "lg:[:root:has([data-call-dock])_&]:h-[calc(100dvh-5rem-1px-var(--call-dock-clearance))]",
          )}
        >
          <div
            ref={directory}
            className={cn(
              "min-h-0 flex-col @[42rem]/messages:flex @[42rem]/messages:border-r @[42rem]/messages:border-brand-line",
              conversationOpen ? "hidden" : "flex",
            )}
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-brand-line px-4 py-3">
              <h1 id={MESSAGES_HEADING_ID} className="font-heading text-xl font-bold leading-tight text-ink">
                Messages
              </h1>
              {canStart ? (
                <GuardedPortalLink
                  href="/portal/messages/new"
                  aria-current={segment === "new" ? "page" : undefined}
                  className={buttonVariants({ className: "min-h-10 px-3" })}
                >
                  <SquarePen size={16} aria-hidden="true" />
                  New message
                </GuardedPortalLink>
              ) : null}
            </div>
            <GuidanceThreadDirectory
              access={access}
              activeThreadId={activeThreadId}
              currentUserId={currentUserId}
              canStart={canStart}
            />
          </div>
          <div
            ref={pane}
            className={cn("min-h-0 min-w-0 flex-col @[42rem]/messages:flex", conversationOpen ? "flex" : "hidden")}
          >
            {children}
          </div>
        </Panel>
      </div>
      <ActionStatus status={status.status} onDismiss={status.dismiss} />
    </GuidanceWorkspaceContext.Provider>
  );
}
