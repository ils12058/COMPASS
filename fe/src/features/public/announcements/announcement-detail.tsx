"use client";

import { Pin } from "lucide-react";
import Link from "next/link";

import { PublicMarkdown } from "@/features/public/shared/public-markdown";
import { formatPublicDate } from "@/features/public/shared/presentation";
import { PublicListSkeleton, PublicSectionError } from "@/features/public/shared/public-state";
import { CompassApiError } from "@/lib/api/errors";
import { useAnnouncementsGetPublic } from "@/lib/api/generated/announcements/announcements";

export function AnnouncementDetail({ announcementId }: { announcementId: string }) {
  const query = useAnnouncementsGetPublic(announcementId);

  if (query.isPending) {
    return <PublicListSkeleton rows={4} />;
  }

  if (query.isError) {
    if (query.error instanceof CompassApiError && query.error.status === 404) {
      return (
        <div className="border-y border-border py-8">
          <h1 className="font-heading text-3xl font-bold text-ink">Announcement not found</h1>
          <p className="mt-3 leading-7 text-muted">
            This announcement does not exist or is no longer publicly available.
          </p>
          <Link className="mt-5 inline-flex min-h-10 items-center font-semibold text-brand hover:underline" href="/announcements">
            Return to announcements
          </Link>
        </div>
      );
    }

    return (
      <PublicSectionError
        message="This announcement could not be loaded."
        onRetry={() => void query.refetch()}
      />
    );
  }

  const announcement = query.data.data;

  return (
    <article aria-busy={query.isFetching}>
      <div className="border-b border-border pb-7">
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
          <time dateTime={announcement.published_at}>{formatPublicDate(announcement.published_at)}</time>
          {announcement.is_pinned ? (
            <span className="inline-flex items-center gap-1 font-semibold text-brand">
              <Pin size={14} aria-hidden="true" />
              Pinned
            </span>
          ) : null}
        </div>
        <h1 className="mt-4 font-heading text-4xl font-bold leading-tight tracking-tight text-ink sm:text-5xl">
          {announcement.title}
        </h1>
      </div>
      <div className="mt-8">
        <PublicMarkdown>{announcement.body_markdown}</PublicMarkdown>
      </div>
      {query.isFetching ? <p role="status" className="mt-6 text-xs text-muted">Refreshing announcement…</p> : null}
    </article>
  );
}
