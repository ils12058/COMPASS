import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { StudentAffiliationsPage } from "@/features/organization/student-affiliations/student-affiliations-page";

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <StudentAffiliationsPage />
    </Suspense>
  );
}
