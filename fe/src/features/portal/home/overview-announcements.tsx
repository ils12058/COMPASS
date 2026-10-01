"use client";

import { Pin } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
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
    <section className="mt-8 border-t border-border pt-6" aria-labelledby="overview-announcements-heading">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1">
        <h2 id="overview-announcements-heading" className="font-heading text-xl font-semibold text-ink">
          Announcements
        </h2>
        <Link href="/announcements" className={linkClass}>All announcements</Link>
      </div>

      {list.isPending ? (
        <div aria-busy="true" className="mt-3 space-y-3">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-5 w-1/2" />
          <p className="sr-only">Loading announcements…</p>
        </div>
      ) : list.isError ? (
        <div role="alert" className="mt-3">
          <p className="text-sm text-muted">
            {signedOut
              ? "Your session has ended. Sign in again to see announcements for your account."
              : "Announcements could not be loaded."}
          </p>
          {signedOut ? null : (
            <Button variant="secondary" className="mt-3" onClick={() => void list.refetch()}>
              Retry
            </Button>
          )}
        </div>
      ) : items.length === 0 ? (
        <p className="mt-3 text-sm text-muted">No current announcements.</p>
      ) : (
        <ul className="mt-3 divide-y divide-border border-y border-border">
          {items.map((announcement) => (
            <li key={announcement.id}>
              <Link
                href={`/announcements/${announcement.id}`}
                className="group grid grid-cols-[3.5rem_minmax(0,1fr)] items-center gap-x-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
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
    </section>
  );
}
