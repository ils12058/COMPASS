import type { Metadata } from "next";

export const metadata: Metadata = { title: "Good Moral Request" };

import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { GoodMoralDetailSkeleton } from "@/features/good-moral/good-moral-shared";
import { GoodMoralDetailPage } from "@/features/good-moral/good-moral-detail-page";

export default async function Page({ params }: { params: Promise<{ requestId: string }> }) {
  const { requestId } = await params;
  return (
    <div className={pageSheetWidth}>
      <Suspense fallback={<GoodMoralDetailSkeleton />}>
        <GoodMoralDetailPage requestId={requestId} />
      </Suspense>
    </div>
  );
}
