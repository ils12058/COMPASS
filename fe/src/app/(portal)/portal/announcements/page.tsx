import { Suspense } from "react";

import { ContentListSkeleton } from "@/features/content/content-shared";
import { AnnouncementsListPage } from "@/features/announcements/announcements-list-page";

export default function Page() {
  return (
    <Suspense fallback={<ContentListSkeleton label="Loading announcements…" />}>
      <AnnouncementsListPage />
    </Suspense>
  );
}
