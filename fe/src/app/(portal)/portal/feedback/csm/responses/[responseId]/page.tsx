import { CsmResponseDetail } from "@/features/feedback/feedback-response-details";

export default async function Page({ params }: { params: Promise<{ responseId: string }> }) {
  const { responseId } = await params;
  return <CsmResponseDetail responseId={responseId} />;
}
