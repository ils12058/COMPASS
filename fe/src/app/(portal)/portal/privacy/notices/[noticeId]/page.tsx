import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { NoticeDetailPage } from "@/features/privacy-governance/notices/notice-detail-page";

export const metadata: Metadata = { title: "Privacy Notice" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <NoticeDetailPage />
    </Suspense>
  );
}
