"use client";

import { ArrowLeft, Pin } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { CompassApiError } from "@/lib/api/client";
import { MarkdownContent } from "@/features/public/components/markdown-content";
import { AnnouncementDetailSkeleton } from "@/features/public/components/public-content-skeletons";
import { formatPublicDate, isUuid } from "@/features/public/utils";
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
  const announcement = query.data?.data;
  const notFound =
    !validId || (query.error instanceof CompassApiError && query.error.status === 404);

  if (notFound) {
    return (
      <div className="public-shell landing-section">
        <Link className="landing-heading-link" href="/announcements">
          <ArrowLeft aria-hidden="true" />
          Back to announcements
        </Link>
        <div className="landing-data-state mt-6">
          <h1 className="font-heading text-2xl font-bold text-[var(--compass-brand-maroon-strong)]">
            Announcement not found
          </h1>
          <p className="mt-2">This announcement is no longer available.</p>
        </div>
      </div>
    );
  }

  if (query.isPending) {
    return (
      <div className="public-shell landing-section">
        <Link className="landing-heading-link" href="/announcements">
          <ArrowLeft aria-hidden="true" />
          Back to announcements
        </Link>
        <div role="status" aria-busy="true">
          <span className="sr-only">Loading announcement…</span>
          <AnnouncementDetailSkeleton />
        </div>
      </div>
    );
  }

  if (query.isError || !announcement) {
    return (
      <div className="public-shell landing-section">
        <Link className="landing-heading-link" href="/announcements">
          <ArrowLeft aria-hidden="true" />
          Back to announcements
        </Link>
        <div className="landing-data-state mt-6">
          <h1 className="font-heading text-2xl font-bold text-[var(--compass-brand-maroon-strong)]">
            Announcement unavailable
          </h1>
          <p className="mt-2">We couldn’t load this announcement right now. Please try again.</p>
          <Button type="button" variant="link" className="mt-3 h-auto p-0" onClick={() => void query.refetch()}>
            Try again
          </Button>
        </div>
      </div>
    );
  }

  const publishedDate = formatPublicDate(announcement.published_at);
  const expiresDate = announcement.expires_at
    ? formatPublicDate(announcement.expires_at)
    : "";

  return (
    <div className="public-shell landing-section">
      <Link className="landing-heading-link" href="/announcements">
        <ArrowLeft aria-hidden="true" />
        Back to announcements
      </Link>

      <article className="landing-paper-sheet mt-6" data-tone="plain">
        <header className="border-b border-[var(--compass-border)] pb-5">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <time dateTime={announcement.published_at}>{publishedDate || "Published"}</time>
            {announcement.is_pinned ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-[var(--compass-brand-gold)]/10 px-2 py-1 font-semibold text-[var(--compass-brand-gold)]">
                <Pin aria-hidden="true" className="size-3" />
                Pinned
              </span>
            ) : null}
            {expiresDate ? <span>Available until {expiresDate}</span> : null}
          </div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-[var(--compass-brand-maroon-strong)] md:text-4xl">
            {announcement.title}
          </h1>
        </header>
        <MarkdownContent source={announcement.body_markdown} className="mt-6 max-w-3xl text-base" />
      </article>
    </div>
  );
}
