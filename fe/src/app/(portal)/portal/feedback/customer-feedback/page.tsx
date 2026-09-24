import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { CustomerFeedbackForm } from "@/features/feedback/customer-feedback-form";

export default function Page() {
  return <Suspense fallback={<Skeleton className="h-96 w-full" />}><CustomerFeedbackForm /></Suspense>;
}
