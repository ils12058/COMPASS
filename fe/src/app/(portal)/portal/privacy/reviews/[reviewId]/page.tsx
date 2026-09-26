import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ReviewDetailPage } from "@/features/privacy-governance/reviews/review-detail-page";

export const metadata: Metadata = { title: "Review" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <ReviewDetailPage />
    </Suspense>
  );
}
