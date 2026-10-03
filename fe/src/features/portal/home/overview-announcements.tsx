"use client";

import { Pin } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { AnnouncementDate } from "@/features/announcements/announcement-date";
import { CompassApiError } from "@/lib/api/errors";
import { useAnnouncementsListVisible } from "@/lib/api/generated/announcements/announcements";

const linkClass =
  "inline-flex min-h-10 items-center text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

// Current Announcements for the signed-in account. The backend decides which
// audiences the account can read; the full lists live on the reader pages.
export function OverviewAnnouncements() {
  const list = useAnnouncementsListVisible({ page: 1, page_size: 3 }, { query: { retry: false } });
  const signedOut = list.error instanceof CompassApiError && list.error.status === 401;
  const items = list.isError ? [] : list.data?.data.items ?? [];

  return (
    <Panel aria-labelledby="overview-announcements-heading">
      <PanelHeader
        title="Announcements"
        titleId="overview-announcements-heading"
        actions={<Link href="/announcements" className={linkClass}>All announcements</Link>}
      />

      {list.isPending ? (
        <div aria-busy="true" className="space-y-3 px-4 py-4 sm:px-5">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-5 w-1/2" />
          <p className="sr-only">Loading announcements…</p>
        </div>
      ) : list.isError ? (
        <PanelMessage
          role="alert"
          action={signedOut ? undefined : (
            <Button variant="secondary" onClick={() => void list.refetch()}>
              Retry
            </Button>
          )}
        >
          {signedOut
            ? "Your session has ended. Sign in again to see announcements for your account."
            : "Announcements could not be loaded."}
        </PanelMessage>
      ) : items.length === 0 ? (
        <PanelMessage>No current announcements.</PanelMessage>
      ) : (
        <ul className="divide-y divide-border">
          {items.map((announcement) => (
            <li key={announcement.id}>
              <Link
                href={`/announcements/${announcement.id}`}
                className="group grid grid-cols-[3.5rem_minmax(0,1fr)] items-center gap-x-4 px-4 py-3 transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus sm:px-5"
              >
                <AnnouncementDate value={announcement.published_at} />
                <span className="min-w-0">
                  <span className="block break-words font-semibold leading-6 text-ink group-hover:text-brand group-hover:underline">
                    {announcement.title}
                  </span>
                  {announcement.is_pinned ? (
                    <span className="mt-1 inline-flex w-fit items-center gap-1 text-xs font-semibold text-brand">
                      <Pin size={13} aria-hidden="true" />
                      Pinned
                    </span>
                  ) : null}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
