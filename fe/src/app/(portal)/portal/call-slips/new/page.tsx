import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { DirectCallSlipCreatePage } from "@/features/call-slips/call-slip-create-page";

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <DirectCallSlipCreatePage />
    </Suspense>
  );
}
