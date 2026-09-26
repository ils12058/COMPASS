import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { NoticeRevisionPage } from "@/features/privacy-governance/notices/notice-revision-page";

export const metadata: Metadata = { title: "Notice revision" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <NoticeRevisionPage />
    </Suspense>
  );
}
