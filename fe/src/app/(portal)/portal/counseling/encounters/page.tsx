import type { Metadata } from "next";
import { Suspense } from "react";

import { CounselingListSkeleton } from "@/features/counseling/counseling-shared";
import { SessionRecordsPage } from "@/features/counseling/session-records-page";

export const metadata: Metadata = { title: "Session records" };

export default function Page() {
  return <Suspense fallback={<CounselingListSkeleton label="Loading session records…" />}><SessionRecordsPage /></Suspense>;
}
