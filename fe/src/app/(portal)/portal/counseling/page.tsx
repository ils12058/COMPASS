import type { Metadata } from "next";
import { Suspense } from "react";

import { CounselingListSkeleton } from "@/features/counseling/counseling-shared";
import { CounselingEntryPage } from "@/features/counseling/counseling-entry-page";

export const metadata: Metadata = { title: "Counseling" };

export default function Page() {
  return <Suspense fallback={<CounselingListSkeleton label="Loading Counseling…" />}><CounselingEntryPage /></Suspense>;
}
