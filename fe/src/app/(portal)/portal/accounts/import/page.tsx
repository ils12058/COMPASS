import type { Metadata } from "next";

export const metadata: Metadata = { title: "Import accounts" };

import { pageSheetWidth } from "@/components/ui/page-width";
import { ImportAccounts } from "@/features/accounts/import/import-accounts";

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <ImportAccounts />
    </div>
  );
}
