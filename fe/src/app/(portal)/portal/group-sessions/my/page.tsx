import type { Metadata } from "next";
import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { GroupSessionsHistoryPage } from "@/features/group-sessions/group-sessions-history-page";

export const metadata: Metadata = { title: "My group sessions" };

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={null}>
        <GroupSessionsHistoryPage />
      </Suspense>
    </div>
  );
}
