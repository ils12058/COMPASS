import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { AnnouncementList } from "@/features/public/announcements/announcement-list";

export function AnnouncementPreview() {
  return (
    <section aria-labelledby="latest-announcements" className="bg-surface-raised">
      <div className="mx-auto max-w-6xl px-5 py-14 sm:px-8 sm:py-18">
        <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
          <h2 id="latest-announcements" className="font-heading text-3xl font-bold tracking-tight text-ink">
            Latest announcements
          </h2>
          <Link
            href="/announcements"
            className="inline-flex min-h-10 items-center gap-2 rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            View all announcements
            <ArrowRight size={17} aria-hidden="true" />
          </Link>
        </div>
        <AnnouncementList mode="preview" />
      </div>
    </section>
  );
}
