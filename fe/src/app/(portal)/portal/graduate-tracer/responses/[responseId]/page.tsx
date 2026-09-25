import { GraduateTracerDetailPage } from "@/features/graduate-tracer/graduate-tracer-detail-page";

export default async function Page({
  params,
}: {
  params: Promise<{ responseId: string }>;
}) {
  const { responseId } = await params;
  return <GraduateTracerDetailPage responseId={responseId} />;
}
