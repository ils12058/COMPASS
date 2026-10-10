"use client";

import Link from "next/link";

import { MarkdownContent } from "@/features/public/components/markdown-content";
import { formatPublicDate, isUuid } from "@/features/public/utils";
import { CompassApiError } from "@/lib/api/client";
import { useAnnouncementsGetPublic } from "@/lib/api/generated/announcements/announcements";

export function AnnouncementDetail({ announcementId }: { announcementId: string }) {
  const validId = isUuid(announcementId);
  const query = useAnnouncementsGetPublic(announcementId, {
    query: {
      enabled: validId,
      retry: false,
      refetchOnWindowFocus: false,
    },
  });

  const notFound =
    !validId || (query.error instanceof CompassApiError && query.error.status === 404);

  if (notFound) {
    return (
      <div className="mx-auto w-full max-w-3xl px-5 py-14 sm:px-8">
        <p className="text-sm font-semibold text-[var(--compass-support-strong)]">Announcements</p>
        <h1 className="mt-2 font-heading text-4xl font-bold">Announcement not found</h1>
        <p className="mt-3 text-muted-foreground">
          This announcement is not available publicly.
        </p>
        <Link href="/announcements" className="mt-6 inline-flex font-semibold">
          Back to announcements
        </Link>
      </div>
    );
  }

  if (query.isPending) {
    return (
      <div className="mx-auto w-full max-w-3xl px-5 py-14 sm:px-8">
        <p role="status" className="text-sm text-muted-foreground">
          Loading announcement…
        </p>
      </div>
    );
  }

  if (query.isError || !query.data) {
    return (
      <div className="mx-auto w-full max-w-3xl px-5 py-14 sm:px-8">
        <h1 className="font-heading text-3xl font-bold">Announcement unavailable</h1>
        <p role="alert" className="mt-3 text-muted-foreground">
          This announcement could not be loaded right now.
        </p>
        <button
          type="button"
          className="mt-5 text-sm font-semibold text-primary underline underline-offset-4"
          onClick={() => query.refetch()}
        >
          Try again
        </button>
      </div>
    );
  }

  const announcement = query.data.data;

  return (
    <article className="mx-auto w-full max-w-3xl px-5 py-10 sm:px-8">
      <Link href="/announcements" className="text-sm font-semibold">
        ← Announcements
      </Link>
      <header className="mt-6 border-b pb-6">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <time dateTime={announcement.published_at}>
            {formatPublicDate(announcement.published_at)}
          </time>
          {announcement.is_pinned ? (
            <span className="rounded-full bg-[var(--compass-brand-gold)]/10 px-2 py-1 text-xs font-semibold text-[var(--compass-brand-gold)]">
              Pinned
            </span>
          ) : null}
        </div>
        <h1 className="mt-3 font-heading text-4xl font-bold tracking-tight">
          {announcement.title}
        </h1>
      </header>
      <div className="pt-4">
        <MarkdownContent source={announcement.body_markdown} />
      </div>
    </article>
  );
}
