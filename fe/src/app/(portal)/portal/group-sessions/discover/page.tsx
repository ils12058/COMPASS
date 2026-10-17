import type { Metadata } from "next";
import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { GroupSessionsDiscoveryPage } from "@/features/group-sessions/group-sessions-discovery-page";

export const metadata: Metadata = { title: "Group Sessions & Workshops" };

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={null}>
        <GroupSessionsDiscoveryPage />
      </Suspense>
    </div>
  );
}
