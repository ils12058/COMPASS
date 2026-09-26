import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { NoticesPage } from "@/features/privacy-governance/notices/notices-page";

export const metadata: Metadata = { title: "Privacy Notices" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <NoticesPage />
    </Suspense>
  );
}
