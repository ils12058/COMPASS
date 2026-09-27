import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { AnnouncementsListPage } from "@/features/announcements/announcements-list-page";

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <AnnouncementsListPage />
    </Suspense>
  );
}
