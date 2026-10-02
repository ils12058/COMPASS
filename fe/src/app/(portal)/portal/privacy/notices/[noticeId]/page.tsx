import type { Metadata } from "next";
import { Suspense } from "react";

import { PrivacyDetailSkeleton } from "@/features/privacy-governance/privacy-governance-shared";
import { NoticeDetailPage } from "@/features/privacy-governance/notices/notice-detail-page";

export const metadata: Metadata = { title: "Privacy Notice" };

export default function Page() {
  return (
    <Suspense fallback={<PrivacyDetailSkeleton label="Loading privacy notice…" />}>
      <NoticeDetailPage />
    </Suspense>
  );
}
