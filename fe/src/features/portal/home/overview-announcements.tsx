"use client";

import { Megaphone, Pin } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { SectionLink } from "@/components/ui/section-link";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPublicDate } from "@/features/public/shared/presentation";
import { CompassApiError } from "@/lib/api/errors";
import { useAnnouncementsListVisible } from "@/lib/api/generated/announcements/announcements";

// Current Announcements for the signed-in account. The backend decides which
// audiences the account can read; the full lists live on the reader pages.
export function OverviewAnnouncements() {
  const list = useAnnouncementsListVisible({ page: 1, page_size: 3 }, { query: { retry: false } });
  const signedOut = list.error instanceof CompassApiError && list.error.status === 401;
  const items = list.isError ? [] : list.data?.data.items ?? [];

  return (
    <Panel className="@container [overflow-wrap:anywhere]" aria-labelledby="overview-announcements-heading">
      <PanelHeader
        className="border-b-0 pb-1"
        title="Announcements"
        titleId="overview-announcements-heading"
        actions={<SectionLink href="/announcements" label="All announcements" icon={Megaphone} />}
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
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-x-6 divide-y divide-border px-4 pb-2 @min-[42rem]:grid-cols-3 @min-[42rem]:divide-y-0 sm:px-5">
          {items.map((announcement) => (
            <li key={announcement.id} className="min-w-0">
              <Link
                href={`/announcements/${announcement.id}`}
                className="group flex min-h-11 min-w-0 flex-col items-start gap-2 rounded-md py-3 transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus"
              >
                <span className="w-full min-w-0 max-w-full">
                  <span className="block [overflow-wrap:anywhere] font-semibold leading-6 text-ink group-hover:text-brand group-hover:underline">
                    {announcement.title}
                  </span>
                  {announcement.is_pinned ? (
                    <span className="mt-1 inline-flex w-fit items-center gap-1 text-xs font-semibold text-brand">
                      <Pin size={13} aria-hidden="true" />
                      Pinned
                    </span>
                  ) : null}
                </span>
                <time dateTime={announcement.published_at} className="text-sm text-muted">{formatPublicDate(announcement.published_at)}</time>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
