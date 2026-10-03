import type { Metadata } from "next";

import { AnnouncementList } from "@/features/public/announcements/announcement-list";
import { PublicPageHeader } from "@/features/public/shared/public-page-header";

export const metadata: Metadata = { title: "Announcements" };

function readPage(value: string | string[] | undefined): number {
  const parsed = Number(Array.isArray(value) ? value[0] : value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

export default async function AnnouncementsPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string | string[] }>;
}) {
  const { page } = await searchParams;

  return (
    <main>
      <PublicPageHeader>
        <h1 className="font-heading text-3xl font-bold tracking-tight text-ink sm:text-4xl">Announcements</h1>
      </PublicPageHeader>
      {/* Same left edge as the page title; the list keeps a readable width. */}
      <div className="mx-auto max-w-6xl px-5 py-7 sm:px-8 sm:py-9">
        <div className="max-w-4xl">
          <AnnouncementList mode="index" page={readPage(page)} />
        </div>
      </div>
    </main>
  );
}
