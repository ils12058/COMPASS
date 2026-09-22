"use client";

import { keepPreviousData } from "@tanstack/react-query";
import { Pin } from "lucide-react";
import Link from "next/link";

import { useAnnouncementsListPublic } from "@/lib/api/generated/announcements/announcements";
import { formatPublicDate } from "@/features/public/shared/presentation";
import { PublicPagination } from "@/features/public/shared/public-pagination";
import { PublicListSkeleton, PublicSectionError } from "@/features/public/shared/public-state";

type AnnouncementListProps =
  | { mode: "preview" }
  | { mode: "index"; page: number };

export function AnnouncementList(props: AnnouncementListProps) {
  const isPreview = props.mode === "preview";
  const page = isPreview ? 1 : props.page;
  const query = useAnnouncementsListPublic(
    { page, page_size: isPreview ? 3 : 10 },
    { query: { placeholderData: keepPreviousData } },
  );

  if (query.isPending) return <PublicListSkeleton rows={isPreview ? 3 : 5} />;

  if (query.isError) {
    return (
      <PublicSectionError
        message="Public announcements could not be loaded."
        onRetry={() => void query.refetch()}
      />
    );
  }

  const result = query.data.data;

  if (result.items.length === 0) {
    return (
      <p className="border-y border-border py-6 text-sm leading-6 text-muted">
        No public announcements are available right now.
      </p>
    );
  }

  return (
    <div aria-busy={query.isFetching}>
      <ol className="divide-y divide-border border-y border-border">
        {result.items.map((announcement) => (
          <li key={announcement.id}>
            <Link
              href={`/announcements/${announcement.id}`}
              className="group grid gap-2 py-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:grid-cols-[9rem_1fr_auto] sm:items-center sm:gap-5"
            >
              <time dateTime={announcement.published_at} className="text-sm text-muted">
                {formatPublicDate(announcement.published_at)}
              </time>
              <span className="font-heading text-lg font-semibold leading-6 text-ink transition-colors group-hover:text-brand">
                {announcement.title}
              </span>
              {announcement.is_pinned ? (
                <span className="inline-flex w-fit items-center gap-1 text-xs font-semibold text-brand">
                  <Pin size={14} aria-hidden="true" />
                  Pinned
                </span>
              ) : null}
            </Link>
          </li>
        ))}
      </ol>

      {query.isFetching && !query.isPending ? (
        <p role="status" className="mt-3 text-xs text-muted">Refreshing announcements…</p>
      ) : null}

      {!isPreview ? (
        <PublicPagination
          page={result.page}
          hasNext={result.has_next}
          buildHref={(nextPage) => `/announcements?page=${nextPage}`}
        />
      ) : null}
    </div>
  );
}
