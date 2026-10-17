"use client";

import { Bell, BellOff, X } from "lucide-react";
import { startTransition, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { useOptionalActiveECounselingCall } from "@/features/ecounseling/runtime/active-call-context";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { reconcileNotificationAuth } from "@/features/notifications/notification-auth";
import {
  createNotificationHeadsUpState,
  dismissNotificationHeadsUp,
  reconcileNotificationHeadsUp,
  shouldPresentNotificationHeadsUp,
} from "@/features/notifications/notification-heads-up-state";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  getNotificationsListMineQueryKey,
  useNotificationsListMine,
} from "@/lib/api/generated/notifications/notifications";

const HEADS_UP_PAGE_SIZE = 20;

function blockingDialogIsOpen(): boolean {
  return document.querySelector(
    '[role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"], dialog[open]',
  ) !== null;
}

function noticeText(count: number): string {
  return count === 1
    ? "You have a new COMPASS notification."
    : "You have new COMPASS notifications.";
}

export function NotificationHeadsUp() {
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
  const activeCall = useOptionalActiveECounselingCall();
  const [muted, setMuted] = useState(false);
  const [state, setState] = useState(createNotificationHeadsUpState);
  const notifications = useNotificationsListMine(
    { page: 1, page_size: HEADS_UP_PAGE_SIZE },
    {
      query: {
        retry: false,
        queryKey: [
          ...getNotificationsListMineQueryKey({ page: 1, page_size: HEADS_UP_PAGE_SIZE }),
          user.id,
        ],
      },
    },
  );

  useEffect(() => {
    if (notifications.error) {
      reconcileNotificationAuth(notifications.error, queryClient);
    }
  }, [notifications.error, queryClient]);

  useEffect(() => {
    if (!notifications.isSuccess || !notifications.data?.data) return;
    const canPresent = shouldPresentNotificationHeadsUp({
      muted,
      activeCall: activeCall?.live ?? false,
      visible: document.visibilityState === "visible",
      blockingDialogOpen: blockingDialogIsOpen(),
    });
    startTransition(() =>
      setState((current) =>
        reconcileNotificationHeadsUp(
          current,
          notifications.data.data.items.map((notification) => notification.id),
          canPresent,
        ),
      ),
    );
  }, [activeCall?.live, muted, notifications.data, notifications.isSuccess]);

  useEffect(() => {
    if (!muted && !activeCall?.live) return;
    startTransition(() =>
      setState((current) => dismissNotificationHeadsUp(current)),
    );
  }, [activeCall?.live, muted]);

  function toggleMute() {
    const nextMuted = !muted;
    setMuted(nextMuted);
    if (nextMuted) setState((current) => dismissNotificationHeadsUp(current));
  }

  const message = state.notice ? noticeText(state.notice.count) : "";

  return (
    <>
      <Button
        type="button"
        variant="quiet"
        className="min-h-11 gap-1.5 px-2 sm:px-2.5"
        aria-label={muted ? "Unmute notification pop-ups" : "Mute notification pop-ups"}
        aria-pressed={muted}
        title={muted ? "Unmute notification pop-ups" : "Mute notification pop-ups"}
        onClick={toggleMute}
      >
        {muted ? (
          <BellOff size={17} aria-hidden="true" />
        ) : (
          <Bell size={17} aria-hidden="true" />
        )}
        <span className="max-sm:sr-only">{muted ? "Unmute" : "Mute"} pop-ups</span>
      </Button>

      {state.notice && !muted && !activeCall?.live ? (
        <div className="pointer-events-none fixed inset-x-4 top-16 z-40 flex justify-end">
          <div className="pointer-events-auto w-full max-w-sm">
            <div
              role="status"
              aria-atomic="true"
              data-notification-heads-up-live
              className="sr-only"
            >
              {message}
            </div>
            <aside
              data-notification-heads-up
              aria-label="New COMPASS notification"
              className="rounded-lg border border-brand-line bg-surface-raised p-4 shadow-dialog"
            >
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold leading-6 text-ink">{message}</p>
                  <GuardedPortalLink
                    href="/portal/notifications"
                    className="mt-2 inline-flex min-h-10 items-center rounded-md text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  >
                    Review notifications
                  </GuardedPortalLink>
                </div>
                <Button
                  type="button"
                  variant="quiet"
                  className="-mr-2 -mt-2 min-h-11 min-w-11 shrink-0 px-0"
                  aria-label="Dismiss notification heads-up"
                  title="Dismiss"
                  onClick={() => setState((current) => dismissNotificationHeadsUp(current))}
                >
                  <X size={18} aria-hidden="true" />
                </Button>
              </div>
            </aside>
          </div>
        </div>
      ) : null}
    </>
  );
}
