import type { Metadata } from "next";

import { ResourceDetail } from "@/features/public/resources/resource-detail";

export const metadata: Metadata = {
  title: "Resource",
};

export default async function ResourcePage({
  params,
}: {
  params: Promise<{ resourceId: string }>;
}) {
  const { resourceId } = await params;
  return <ResourceDetail resourceId={resourceId} />;
}
