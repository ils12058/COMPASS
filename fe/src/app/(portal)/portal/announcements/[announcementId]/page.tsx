import type { Metadata } from "next";
import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { ContentDetailSkeleton } from "@/features/content/content-shared";
import { AnnouncementDetailPage } from "@/features/announcements/announcement-detail-page";

export const metadata: Metadata = { title: "Announcement" };

export default async function Page({
  params,
}: {
  params: Promise<{ announcementId: string }>;
}) {
  const { announcementId } = await params;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<ContentDetailSkeleton label="Loading Announcement…" />}>
        <AnnouncementDetailPage key={announcementId} announcementId={announcementId} />
      </Suspense>
    </div>
  );
}
