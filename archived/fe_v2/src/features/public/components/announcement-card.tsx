import { Pin } from "lucide-react";
import Link from "next/link";

import type { AnnouncementReaderResponse } from "@/lib/api/generated/model";

import { MarkdownContent } from "./markdown-content";

import { formatPublicDate } from "@/features/public/utils";

export function AnnouncementCard({
  announcement,
  compact = false,
}: {
  announcement: AnnouncementReaderResponse;
  compact?: boolean;
}) {
  const date = formatPublicDate(announcement.published_at);

  return (
    <article className="landing-paper-sheet h-full" data-tone="plain">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <time dateTime={announcement.published_at}>{date || "Published"}</time>
        {announcement.is_pinned ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-[var(--compass-brand-gold)]/10 px-2 py-1 font-semibold text-[var(--compass-brand-gold)]">
            <Pin aria-hidden="true" className="size-3" />
            Pinned
          </span>
        ) : null}
      </div>
      <h2 className={compact ? "font-heading text-lg font-bold" : "font-heading text-xl font-bold"}>
        <Link href={`/announcements/${announcement.id}`} className="no-underline hover:underline">
          {announcement.title}
        </Link>
      </h2>
      <MarkdownContent source={announcement.body_markdown} compact />
      <Link
        href={`/announcements/${announcement.id}`}
        className="mt-4 inline-flex text-sm font-semibold"
      >
        Read announcement <span aria-hidden="true">↗</span>
      </Link>
    </article>
  );
}
