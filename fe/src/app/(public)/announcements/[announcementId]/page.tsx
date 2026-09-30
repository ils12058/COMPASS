import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AnnouncementDetail } from "@/features/public/announcements/announcement-detail";
import {
  isReaderUuid,
  resolveAnnouncementReader,
} from "@/features/public/shared/server-reader";

const description = "Announcement from the UCN Guidance and Counseling Office.";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ announcementId: string }>;
}): Promise<Metadata> {
  const { announcementId } = await params;
  if (!isReaderUuid(announcementId)) {
    return { title: "Announcement", description };
  }

  const resolution = await resolveAnnouncementReader(announcementId);
  return {
    title: resolution.kind === "available" ? resolution.title : "Announcement",
    description,
  };
}

export default async function AnnouncementDetailPage({
  params,
}: {
  params: Promise<{ announcementId: string }>;
}) {
  const { announcementId } = await params;
  if (!isReaderUuid(announcementId)) notFound();

  const resolution = await resolveAnnouncementReader(announcementId);
  if (resolution.kind === "not-found") notFound();

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
