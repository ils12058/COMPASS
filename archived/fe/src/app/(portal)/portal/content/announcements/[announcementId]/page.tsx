import { AnnouncementEditorPage } from "@/features/content/announcements/announcement-editor-page";

export default async function AnnouncementManagementDetailPage({
  params,
}: {
  params: Promise<{ announcementId: string }>;
}) {
  const { announcementId } = await params;
  return <AnnouncementEditorPage announcementId={announcementId} />;
}
