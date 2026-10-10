"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { AnnouncementCard } from "@/features/public/components/announcement-card";
import { AnnouncementCardSkeleton } from "@/features/public/components/public-content-skeletons";
import { PublicContentPagination } from "@/features/public/components/public-content-pagination";
import { useAnnouncementsListPublic } from "@/lib/api/generated/announcements/announcements";

const PAGE_SIZE = 10;

export function AnnouncementsIndex() {
  const [page, setPage] = useState(1);
  const query = useAnnouncementsListPublic(
    { page, page_size: PAGE_SIZE },
    { query: { retry: 1, refetchOnWindowFocus: false } },
  );
  const items = query.data?.data?.items ?? [];

  return (
    <div className="public-shell landing-section" aria-labelledby="announcements-page-heading">
      <header className="mb-8 space-y-2">
        <h1 id="announcements-page-heading" className="font-heading text-4xl font-bold tracking-tight">
          Announcements
        </h1>
        <p className="max-w-2xl text-muted-foreground">
          Important updates and reminders for UCNians from the Guidance and Counseling Office.
        </p>
      </header>

      {query.isFetching && query.data ? (
        <p role="status" className="mb-4 text-sm text-muted-foreground">
          Updating announcements…
        </p>
      ) : null}

      {query.isPending ? (
        <div className="grid gap-4" role="status" aria-busy="true">
          <span className="sr-only">Loading announcements…</span>
          {Array.from({ length: 6 }, (_, index) => (
            <AnnouncementCardSkeleton key={index} />
          ))}
        </div>
      ) : query.isError ? (
        <div className="landing-data-state">
          <p role="alert">We couldn’t load announcements right now. Please try again.</p>
          <Button
            type="button"
            variant="link"
            className="mt-3 h-auto p-0"
            onClick={() => void query.refetch()}
          >
            Try again
          </Button>
        </div>
      ) : items.length === 0 ? (
        <p className="landing-data-state">
          No announcements to show right now.
        </p>
      ) : (
        <div className="grid gap-4">
          {items.map((item) => (
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
