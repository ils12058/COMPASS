import type { Metadata } from "next";

import { AnnouncementCreatePage } from "@/features/announcements/announcement-create-page";

export const metadata: Metadata = { title: "Create Announcement" };

export default function Page() {
  return <AnnouncementCreatePage />;
}
