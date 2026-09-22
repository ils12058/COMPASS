import type { Metadata } from "next";
import Link from "next/link";

import { AnnouncementDetail } from "@/features/public/announcements/announcement-detail";

export const metadata: Metadata = { title: "Announcement" };

export default async function AnnouncementDetailPage({
  params,
}: {
  params: Promise<{ announcementId: string }>;
}) {
  const { announcementId } = await params;

  return (
    <main className="bg-surface">
      <div className="mx-auto max-w-3xl px-5 py-10 sm:px-8 sm:py-14">
        <Link href="/announcements" className="mb-7 inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
          Back to announcements
        </Link>
        <AnnouncementDetail announcementId={announcementId} />
      </div>
    </main>
  );
}
