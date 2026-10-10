import { AssessmentRecordDetailPage } from "@/features/assessment-records/assessment-record-detail";
export default async function Page({
  params,
}: {
  params: Promise<{ recordId: string }>;
}) {
  const { recordId } = await params;
  return <AssessmentRecordDetailPage recordId={recordId} />;
}
