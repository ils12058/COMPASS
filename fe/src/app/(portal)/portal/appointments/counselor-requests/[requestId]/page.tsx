import { HeadCounselorRequestDetailPage } from "@/features/appointments/head-counselor-request-detail-page";

export default async function PortalCounselorRequestDetailPage({
  params,
}: {
  params: Promise<{ requestId: string }>;
}) {
  const { requestId } = await params;
  return <HeadCounselorRequestDetailPage requestId={requestId} />;
}
