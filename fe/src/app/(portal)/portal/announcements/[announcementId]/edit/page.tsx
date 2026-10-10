import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { AnnouncementEditPage } from "@/features/announcements/announcement-edit-page";

export const metadata: Metadata = { title: "Edit Announcement" };

export default async function Page({
  params,
}: {
  params: Promise<{ announcementId: string }>;
}) {
  const { announcementId } = await params;
  return (
    <div className={pageSheetWidth}>
      <AnnouncementEditPage key={announcementId} announcementId={announcementId} />
    </div>
  );
}
