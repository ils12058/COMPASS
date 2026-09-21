"use client";

import Link from "next/link";

import { MarkdownContent } from "@/features/public/components/markdown-content";
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
      className="public-shell landing-section"
      aria-labelledby="announcements-heading"
    >
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

      {query.isPending ? (
        <p role="status" className="landing-data-state">
          Loading announcements…
        </p>
      ) : query.isError ? (
        <p role="status" className="landing-data-state">
          We couldn’t load announcements right now. Please try again later.
        </p>
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
    </section>
  );
}
