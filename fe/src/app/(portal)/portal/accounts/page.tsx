import { Suspense } from "react";

import { AccountsList, AccountsListSkeleton } from "@/features/accounts/list/accounts-list";

export default function Page() {
  return (
    <Suspense fallback={<AccountsListSkeleton />}>
      <AccountsList />
    </Suspense>
  );
}
