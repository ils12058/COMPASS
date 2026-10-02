import type { Metadata } from "next";
import { Suspense } from "react";

import { ContentDetailSkeleton } from "@/features/content/content-shared";
import { ResourceDetailPage } from "@/features/resources/resource-detail-page";

export const metadata: Metadata = { title: "Resource" };

export default async function Page({
  params,
}: {
  params: Promise<{ resourceId: string }>;
}) {
  const { resourceId } = await params;
  return (
    <Suspense fallback={<ContentDetailSkeleton label="Loading Resource…" />}>
      <ResourceDetailPage key={resourceId} resourceId={resourceId} />
    </Suspense>
  );
}
