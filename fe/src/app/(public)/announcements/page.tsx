import type { Metadata } from "next";

import { AnnouncementList } from "@/features/public/announcements/announcement-list";
import { readOrdering } from "@/features/portal/components/list-ordering-params";
import { AnnouncementOrdering } from "@/lib/api/generated/model";
import { PublicPageHeader } from "@/features/public/shared/public-page-header";

export const metadata: Metadata = { title: "Announcements" };

function readPage(value: string | string[] | undefined): number {
  const parsed = Number(Array.isArray(value) ? value[0] : value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function AnnouncementsPage({
  searchParams,
}: {
  searchParams: Promise<{
    page?: string | string[];
    search?: string | string[];
    ordering?: string | string[];
  }>;
}) {
  const { page, search, ordering } = await searchParams;

  return (
    <main>
      <PublicPageHeader
        illustration={{ src: "/illustrations/gco-character-point-up.png", width: 330, height: 330 }}
      >
        <h1 className="font-heading text-3xl font-bold tracking-tight text-ink sm:text-4xl">Announcements</h1>
      </PublicPageHeader>
      {/* Same left edge as the page title; the list keeps a readable width. */}
      <div className="mx-auto max-w-6xl px-5 py-7 sm:px-8 sm:py-9">
        <div className="max-w-4xl">
          <AnnouncementList
            mode="index"
            page={readPage(page)}
            search={first(search)?.trim() || undefined}
            ordering={readOrdering(first(ordering) ?? null, AnnouncementOrdering)}
          />
        </div>
      </div>
    </main>
  );
}
