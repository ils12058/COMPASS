import type { Metadata } from "next";

export const metadata: Metadata = { title: "Feedback Response Details" };

import { pageSheetWidth } from "@/components/ui/page-width";
import { CustomerFeedbackResponseDetail } from "@/features/feedback/feedback-response-details";

export default async function Page({ params }: { params: Promise<{ responseId: string }> }) {
  const { responseId } = await params;
  return (
    <div className={pageSheetWidth}>
      <CustomerFeedbackResponseDetail responseId={responseId} />
    </div>
  );
}
