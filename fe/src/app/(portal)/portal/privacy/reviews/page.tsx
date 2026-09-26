import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ReviewsPage } from "@/features/privacy-governance/reviews/reviews-page";

export const metadata: Metadata = { title: "Reviews & PIAs" };

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <ReviewsPage />
    </Suspense>
  );
}
