import type { Metadata } from "next";
import { Suspense } from "react";
import { pageSheetWidth } from "@/components/ui/page-width";
import { TransferReviewPage } from "@/features/counseling/continuity/transfer-review-page";
import { EncounterDetailSkeleton } from "@/features/counseling/counseling-shared";

export const metadata: Metadata = { title: "Transfer review" };
export default async function Page({ params }: { params: Promise<{ transferId: string }> }) {
  const { transferId } = await params;
  return <div className={pageSheetWidth}><Suspense fallback={<EncounterDetailSkeleton />}><TransferReviewPage transferId={transferId} /></Suspense></div>;
}
