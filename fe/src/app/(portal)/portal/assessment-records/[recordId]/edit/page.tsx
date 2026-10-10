import { AssessmentRecordEditorPage } from "@/features/assessment-records/assessment-record-editor";
export default async function Page({
  params,
}: {
  params: Promise<{ recordId: string }>;
}) {
  const { recordId } = await params;
  return <AssessmentRecordEditorPage recordId={recordId} />;
}
