import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { ResourceEditPage } from "@/features/resources/resource-edit-page";

export const metadata: Metadata = { title: "Edit Resource" };

export default async function Page({
  params,
}: {
  params: Promise<{ resourceId: string }>;
}) {
  const { resourceId } = await params;
  return (
    <div className={pageSheetWidth}>
      <ResourceEditPage key={resourceId} resourceId={resourceId} />
    </div>
  );
}
