import type { Metadata } from "next";

import { AnnouncementsIndex } from "@/features/public/announcements/announcements-index";

export const metadata: Metadata = {
  title: "Announcements",
};

export default function AnnouncementsPage() {
  return <AnnouncementsIndex />;
}
