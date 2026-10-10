import type { Metadata } from "next";
import { Suspense } from "react";

import { PrivacyListSkeleton } from "@/features/privacy-governance/privacy-governance-shared";
import { NoticesPage } from "@/features/privacy-governance/notices/notices-page";

export const metadata: Metadata = { title: "Privacy Notices" };

export default function Page() {
  return (
    <Suspense fallback={<PrivacyListSkeleton label="Loading privacy notices…" />}>
      <NoticesPage />
    </Suspense>
  );
}
