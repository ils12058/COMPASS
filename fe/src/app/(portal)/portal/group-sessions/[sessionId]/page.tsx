import type { Metadata } from "next";
import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { GroupSessionDetailPage } from "@/features/group-sessions/group-session-detail-page";

export const metadata: Metadata = { title: "Group session details" };

export default async function Page({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={null}>
        <GroupSessionDetailPage sessionId={sessionId} />
      </Suspense>
    </div>
  );
}
