import type { ReactNode } from "react";

import { AccountDetailFrame } from "@/features/accounts/detail/account-detail-frame";

export default async function AccountLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ userId: string }>;
}) {
  const { userId } = await params;
  return <AccountDetailFrame userId={userId}>{children}</AccountDetailFrame>;
}
