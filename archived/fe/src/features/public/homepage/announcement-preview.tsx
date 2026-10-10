"use client";

import Link from "next/link";

import { AnnouncementCard } from "@/features/public/components/announcement-card";
import { useAnnouncementsListPublic } from "@/lib/api/generated/announcements/announcements";

export function AnnouncementPreview() {
  const query = useAnnouncementsListPublic(
    { page: 1, page_size: 3 },
    { query: { retry: 1, refetchOnWindowFocus: false } },
  );

  return (
    <section className="mx-auto w-full max-w-7xl px-5 py-12 sm:px-8" aria-labelledby="announcements-heading">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[var(--compass-support-strong)]">Stay informed</p>
          <h2 id="announcements-heading" className="mt-1 font-heading text-3xl font-bold">
            Announcements
          </h2>
        </div>
        <Link href="/announcements" className="text-sm font-semibold">
          View all announcements
        </Link>
      </div>

      {query.isPending ? (
        <p role="status" className="rounded-xl border bg-card p-5 text-sm text-muted-foreground">
          Loading announcements…
        </p>
      ) : query.isError ? (
        <p role="status" className="rounded-xl border bg-card p-5 text-sm text-muted-foreground">
          Announcements are temporarily unavailable. The rest of COMPASS remains available.
        </p>
      ) : query.data.data.items.length === 0 ? (
        <p className="rounded-xl border bg-card p-5 text-sm text-muted-foreground">
          There are no public announcements right now.
        </p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          {query.data.data.items.map((item) => (
            <AnnouncementCard key={item.id} announcement={item} compact />
          ))}
        </div>
      )}
    </section>
  );
}
