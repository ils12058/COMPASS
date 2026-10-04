import type { Metadata } from "next";
import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { PrivacyDetailSkeleton } from "@/features/privacy-governance/privacy-governance-shared";
import { NoticeRevisionPage } from "@/features/privacy-governance/notices/notice-revision-page";

export const metadata: Metadata = { title: "Notice revision" };

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<PrivacyDetailSkeleton label="Loading notice revision…" />}>
        <NoticeRevisionPage />
      </Suspense>
    </div>
  );
}
