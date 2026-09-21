import { ResourceEditorPage } from "@/features/content/resources/resource-editor-page";

export default async function ResourceManagementDetailPage({
  params,
}: {
  params: Promise<{ resourceId: string }>;
}) {
  const { resourceId } = await params;
  return <ResourceEditorPage resourceId={resourceId} />;
}
