import type { Metadata } from "next";

export const metadata: Metadata = { title: "CSM Response Details" };

import { pageSheetWidth } from "@/components/ui/page-width";
import { CsmResponseDetail } from "@/features/feedback/feedback-response-details";

export default async function Page({ params }: { params: Promise<{ responseId: string }> }) {
  const { responseId } = await params;
  return (
    <div className={pageSheetWidth}>
      <CsmResponseDetail responseId={responseId} />
    </div>
  );
}
