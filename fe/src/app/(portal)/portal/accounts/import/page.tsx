import type { Metadata } from "next";

export const metadata: Metadata = { title: "Import Accounts" };

import { ImportAccounts } from "@/features/accounts/import/import-accounts";

export default function Page() {
  return <ImportAccounts />;
}
