import type { ReactNode } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { AccountDetailFrame } from "@/features/accounts/detail/account-detail-frame";

export default async function AccountLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ userId: string }>;
}) {
  const { userId } = await params;
  return (
    <div className={pageSheetWidth}>
      <AccountDetailFrame userId={userId}>{children}</AccountDetailFrame>
    </div>
  );
}
