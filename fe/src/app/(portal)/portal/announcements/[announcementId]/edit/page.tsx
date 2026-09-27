import type { Metadata } from "next";

import { AnnouncementEditPage } from "@/features/announcements/announcement-edit-page";

export const metadata: Metadata = { title: "Edit Announcement" };

export default async function Page({
  params,
}: {
  params: Promise<{ announcementId: string }>;
}) {
  const { announcementId } = await params;
  return <AnnouncementEditPage key={announcementId} announcementId={announcementId} />;
}
