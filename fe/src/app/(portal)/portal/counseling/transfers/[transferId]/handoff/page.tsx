import type { Metadata } from "next";
import { Suspense } from "react";
import { pageSheetWidth } from "@/components/ui/page-width";
import { CaseHandoffPage } from "@/features/counseling/continuity/case-handoff-page";
import { EncounterDetailSkeleton } from "@/features/counseling/counseling-shared";

export const metadata: Metadata = { title: "Case handoff" };
export default async function Page({ params }: { params: Promise<{ transferId: string }> }) {
  const { transferId } = await params;
  return <div className={pageSheetWidth}><Suspense fallback={<EncounterDetailSkeleton />}><CaseHandoffPage transferId={transferId} /></Suspense></div>;
}
