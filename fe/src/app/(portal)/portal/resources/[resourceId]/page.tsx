import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ResourceDetailPage } from "@/features/resources/resource-detail-page";

export const metadata: Metadata = { title: "Resource" };

export default async function Page({
  params,
}: {
  params: Promise<{ resourceId: string }>;
}) {
  const { resourceId } = await params;
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <ResourceDetailPage key={resourceId} resourceId={resourceId} />
    </Suspense>
  );
}
