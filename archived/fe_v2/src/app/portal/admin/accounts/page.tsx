import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Accounts",
};

export default function ItAdminAccountsPage() {
  return <PortalItAdminPage section="accounts" />;
}
