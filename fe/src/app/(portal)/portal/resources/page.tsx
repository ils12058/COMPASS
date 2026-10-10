import { Suspense } from "react";

import { ContentListSkeleton } from "@/features/content/content-shared";
import { ResourcesListPage } from "@/features/resources/resources-list-page";

export default function Page() {
  return (
    <Suspense fallback={<ContentListSkeleton label="Loading Resources…" />}>
      <ResourcesListPage />
    </Suspense>
  );
}
