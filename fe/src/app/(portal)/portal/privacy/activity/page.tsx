import type { Metadata } from "next";
import { Suspense } from "react";

import { PrivacyListSkeleton } from "@/features/privacy-governance/privacy-governance-shared";
import { PrivacyActivityPage } from "@/features/privacy-governance/activity/privacy-activity-page";

export const metadata: Metadata = { title: "Privacy & Security Activity" };

export default function Page() {
  return (
    <Suspense fallback={<PrivacyListSkeleton label="Loading privacy and security activity…" />}>
      <PrivacyActivityPage />
    </Suspense>
  );
}
