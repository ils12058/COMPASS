import type { Metadata } from "next";
import { Suspense } from "react";
import { pageSheetWidth } from "@/components/ui/page-width";
import { EncounterDetailSkeleton } from "@/features/counseling/counseling-shared";
import { ProposeSessionPage } from "@/features/counseling/session-proposals/propose-session-page";

export const metadata: Metadata = { title: "Propose session" };

export default async function Page({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  return <div className={pageSheetWidth}><Suspense fallback={<EncounterDetailSkeleton />}><ProposeSessionPage caseId={caseId} /></Suspense></div>;
}
