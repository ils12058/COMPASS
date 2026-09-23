import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { CollegesPage } from "@/features/organization/colleges/colleges-page";

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <CollegesPage />
    </Suspense>
  );
}
