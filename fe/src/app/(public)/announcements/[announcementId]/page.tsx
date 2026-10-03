import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { pageBackLinkClass } from "@/components/ui/page-header";
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
    return {
      title: "Announcement",
      description,
      robots: { index: false, follow: false },
    };
  }

  const resolution = await resolveAnnouncementReader(announcementId);
  return {
    title: resolution.kind === "available" ? resolution.title : "Announcement",
    description,
    robots:
      resolution.kind === "available" && resolution.indexable
        ? undefined
        : { index: false, follow: false },
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
    <main>
      <div className="mx-auto max-w-6xl px-5 py-7 sm:px-8 sm:py-9">
        <div className="max-w-4xl">
          <Link href="/announcements" className={pageBackLinkClass}>
            Back to announcements
          </Link>
          <AnnouncementDetail announcementId={announcementId} />
        </div>
      </div>
    </main>
  );
}
