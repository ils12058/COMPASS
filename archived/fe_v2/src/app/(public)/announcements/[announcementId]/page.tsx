import type { Metadata } from "next";

import { AnnouncementDetail } from "@/features/public/announcements/announcement-detail";

export const metadata: Metadata = {
  title: "Announcement",
};

export default async function AnnouncementPage({
  params,
}: {
  params: Promise<{ announcementId: string }>;
}) {
  const { announcementId } = await params;
  return <AnnouncementDetail announcementId={announcementId} />;
}
