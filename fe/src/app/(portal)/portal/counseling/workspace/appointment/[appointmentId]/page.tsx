import type { Metadata } from "next";

export const metadata: Metadata = { title: "Counseling Workspace" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { CounselingWorkspaceSkeleton } from "@/features/counseling/counseling-shared";
import { CounselingWorkspace } from "@/features/counseling/counseling-workspace";
import { CounselingContextAnchorType } from "@/lib/api/generated/model";

export default async function Page({ params }: { params: Promise<{ appointmentId: string }> }) {
  const { appointmentId } = await params;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<CounselingWorkspaceSkeleton />}><CounselingWorkspace anchorType={CounselingContextAnchorType.APPOINTMENT} anchorId={appointmentId} /></Suspense>
    </div>
  );
}
