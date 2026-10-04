import type { Metadata } from "next";

export const metadata: Metadata = { title: "Exit Interview Details" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { ExitInterviewDetailSkeleton } from "@/features/exit-interviews/exit-interview-shared";
import { ExitInterviewDetailPage } from "@/features/exit-interviews/exit-interview-detail-page";

export default async function Page({
  params,
}: {
  params: Promise<{ exitInterviewId: string }>;
}) {
  const { exitInterviewId } = await params;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<ExitInterviewDetailSkeleton />}>
        <ExitInterviewDetailPage exitInterviewId={exitInterviewId} />
      </Suspense>
    </div>
  );
}
