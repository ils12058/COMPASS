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
        <h1 className="font-heading text-4xl font-bold tracking-tight text-ink">Announcements</h1>
      </PublicPageHeader>
      <div className="mx-auto max-w-4xl px-5 py-10 sm:px-8 sm:py-14">
        <AnnouncementList mode="index" page={readPage(page)} />
      </div>
    </main>
  );
}
