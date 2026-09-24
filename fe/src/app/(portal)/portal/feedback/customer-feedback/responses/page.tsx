import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { CustomerFeedbackResponseList } from "@/features/feedback/feedback-response-lists";

export default function Page() {
  return <Suspense fallback={<Skeleton className="h-96 w-full" />}><CustomerFeedbackResponseList /></Suspense>;
}
