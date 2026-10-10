import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { pageBackLinkClass } from "@/components/ui/page-header";
import { AnnouncementDetail } from "@/features/public/announcements/announcement-detail";
import { listReturnHref } from "@/features/content/list-return-href";
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
  searchParams,
}: {
  params: Promise<{ announcementId: string }>;
  searchParams: Promise<{ search?: string | string[]; page?: string | string[] }>;
}) {
  const { announcementId } = await params;
  const listParams = await searchParams;
  const backParams = new URLSearchParams();
  for (const key of ["search", "page"] as const) {
    const value = listParams[key];
    if (typeof value === "string") backParams.set(key, value);
    else if (value?.[0]) backParams.set(key, value[0]);
  }
  if (!isReaderUuid(announcementId)) notFound();

  const resolution = await resolveAnnouncementReader(announcementId);
  if (resolution.kind === "not-found") notFound();

  return (
    <main>
      <div className="mx-auto max-w-6xl px-5 py-7 sm:px-8 sm:py-9">
        <div className="max-w-4xl">
          <Link href={listReturnHref("/announcements", backParams, ["search", "page"])} className={pageBackLinkClass}>
            Back to announcements
          </Link>
          <AnnouncementDetail announcementId={announcementId} />
        </div>
      </div>
    </main>
  );
}
