import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { AnnouncementDetailPage } from "@/features/announcements/announcement-detail-page";

export const metadata: Metadata = { title: "Announcement" };

export default async function Page({
  params,
}: {
  params: Promise<{ announcementId: string }>;
}) {
  const { announcementId } = await params;
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <AnnouncementDetailPage key={announcementId} announcementId={announcementId} />
    </Suspense>
  );
}
