import type { Metadata } from "next";
import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { OpenCasePage } from "@/features/counseling/cases/open-case-page";
import { CounselingWorkspaceSkeleton } from "@/features/counseling/counseling-shared";

export const metadata: Metadata = { title: "Open case" };

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<CounselingWorkspaceSkeleton />}><OpenCasePage /></Suspense>
    </div>
  );
}
