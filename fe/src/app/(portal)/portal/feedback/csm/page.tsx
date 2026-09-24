import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { CsmForm } from "@/features/feedback/csm-form";

export default function Page() {
  return <Suspense fallback={<Skeleton className="h-96 w-full" />}><CsmForm /></Suspense>;
}
