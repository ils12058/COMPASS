import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { AnnouncementCreatePage } from "@/features/announcements/announcement-create-page";

export const metadata: Metadata = { title: "Create Announcement" };

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <AnnouncementCreatePage />
    </div>
  );
}
