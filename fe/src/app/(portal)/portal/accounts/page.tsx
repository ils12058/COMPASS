import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { AccountsList } from "@/features/accounts/list/accounts-list";

export default function Page() {
  return (
    <Suspense
      fallback={
        <div aria-busy="true">
          <Skeleton className="h-10 w-52" />
          <Skeleton className="mt-8 h-12 w-full" />
        </div>
      }
    >
      <AccountsList />
    </Suspense>
  );
}
