import type { Metadata } from "next";

export const metadata: Metadata = { title: "Create Account" };

import { pageSheetWidth } from "@/components/ui/page-width";
import { CreateAccount } from "@/features/accounts/create/create-account";

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <CreateAccount />
    </div>
  );
}
