import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { CounselingEntryPage } from "@/features/counseling/counseling-entry-page";

export const metadata: Metadata = { title: "Counseling" };

export default function Page() {
  return <Suspense fallback={<Skeleton className="h-96 w-full" />}><CounselingEntryPage /></Suspense>;
}
