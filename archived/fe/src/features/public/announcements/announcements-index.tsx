"use client";

import { useState } from "react";

import { AnnouncementCard } from "@/features/public/components/announcement-card";
import { PublicContentPagination } from "@/features/public/components/public-content-pagination";
import { useAnnouncementsListPublic } from "@/lib/api/generated/announcements/announcements";

const PAGE_SIZE = 10;

export function AnnouncementsIndex() {
  const [page, setPage] = useState(1);
  const query = useAnnouncementsListPublic(
    { page, page_size: PAGE_SIZE },
    { query: { retry: 1, refetchOnWindowFocus: false } },
  );

  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-10 sm:px-8">
      <header className="mb-8 space-y-2">
        <p className="text-sm font-semibold text-[var(--compass-support-strong)]">
          Guidance and Counseling Office
        </p>
        <h1 className="font-heading text-4xl font-bold tracking-tight">Announcements</h1>
        <p className="max-w-2xl text-muted-foreground">
          Public updates and notices from the Guidance and Counseling Office.
        </p>
      </header>

      {query.isPending ? (
        <p role="status" className="rounded-xl border bg-card p-6 text-sm text-muted-foreground">
          Loading announcements…
        </p>
      ) : query.isError ? (
        <div className="rounded-xl border bg-card p-6">
          <p role="alert" className="text-sm text-muted-foreground">
            Announcements are temporarily unavailable.
          </p>
          <button
            type="button"
            className="mt-3 text-sm font-semibold text-primary underline underline-offset-4"
            onClick={() => query.refetch()}
          >
            Try again
          </button>
        </div>
      ) : query.data.data.items.length === 0 ? (
        <p className="rounded-xl border bg-card p-6 text-sm text-muted-foreground">
          There are no public announcements on this page.
        </p>
      ) : (
        <div className="grid gap-4">
          {query.data.data.items.map((item) => (
            <AnnouncementCard key={item.id} announcement={item} />
          ))}
        </div>
      )}

      {query.data ? (
        <div className="mt-8">
          <PublicContentPagination
            page={page}
            hasNext={query.data.data.has_next}
            onPageChange={setPage}
          />
        </div>
      ) : null}
    </div>
  );
}
