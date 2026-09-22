"use client";

import { Megaphone } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { MarkdownContent } from "@/features/public/components/markdown-content";
import { AnnouncementCardSkeleton } from "@/features/public/components/public-content-skeletons";
import { LANDING_PAGE } from "@/features/public/config";
import { formatPublicDate } from "@/features/public/utils";
import { useAnnouncementsListPublic } from "@/lib/api/generated/announcements/announcements";

import { ArrowLink, StickyNote } from "./preview-primitives";

const NOTE_STYLES = [
  { tone: "butter", rotation: "left" },
  { tone: "sage", rotation: "right" },
  { tone: "rose", rotation: "left" },
] as const;

export function AnnouncementPreview() {
  const { announcements } = LANDING_PAGE;
  const query = useAnnouncementsListPublic(
    { page: 1, page_size: 3 },
    { query: { retry: 1, refetchOnWindowFocus: false } },
  );
  const items = query.data?.data?.items ?? [];

  return (
    <section
      className="landing-section-band landing-announcements"
      aria-labelledby="announcements-heading"
    >
      <Megaphone
        aria-hidden="true"
        className="landing-section-band__icon landing-section-band__icon--announcements"
      />
      <div className="public-shell landing-section">
        <div className="landing-section__heading">
          <div>
            <p className="landing-eyebrow">{announcements.eyebrow}</p>
            <h2 id="announcements-heading">{announcements.title}</h2>
            <p>{announcements.description}</p>
          </div>
          <Link className="landing-heading-link" href={announcements.href}>
            {announcements.link}
            <span aria-hidden="true">→</span>
          </Link>
        </div>

        {query.isFetching && query.data ? (
          <p role="status" className="mb-4 text-sm text-muted-foreground">
            Updating announcements…
          </p>
        ) : null}

        {query.isPending ? (
          <div className="landing-notes-grid" role="status" aria-busy="true">
            <span className="sr-only">Loading announcements…</span>
            {Array.from({ length: 3 }, (_, index) => (
              <AnnouncementCardSkeleton key={index} compact />
            ))}
          </div>
        ) : query.isError ? (
          <div className="landing-data-state">
            <p role="alert">We couldn’t load announcements right now.</p>
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
          <div className="landing-notes-grid">
            {items.map((item, index) => {
              const style = NOTE_STYLES[index % NOTE_STYLES.length];
              const date = formatPublicDate(item.published_at);
              const meta = [item.is_pinned ? "Pinned" : null, date]
                .filter(Boolean)
                .join(" · ");

              return (
                <StickyNote
                  key={item.id}
                  tone={style.tone}
                  rotation={style.rotation}
                >
                  <p className="landing-content-meta">{meta || "Office update"}</p>
                  <h3>{item.title}</h3>
                  <MarkdownContent source={item.body_markdown} compact />
                  <ArrowLink href={`/announcements/${item.id}`}>
                    Read announcement
                  </ArrowLink>
                </StickyNote>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
