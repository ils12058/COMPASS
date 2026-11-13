import type { Metadata } from "next";
import { Suspense } from "react";
import { pageSheetWidth } from "@/components/ui/page-width";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { StudentSessionProposalPage } from "@/features/counseling/session-proposals/student-session-proposal-page";

export const metadata: Metadata = { title: "Proposed session" };

export default async function Page({ params }: { params: Promise<{ proposalId: string }> }) {
  const { proposalId } = await params;
  return <div className={pageSheetWidth}><Suspense fallback={<RowsSkeleton label="Loading proposed session…" />}><StudentSessionProposalPage proposalId={proposalId} /></Suspense></div>;
}
