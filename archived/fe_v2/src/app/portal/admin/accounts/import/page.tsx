import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Import accounts",
};

export default function ItAdminImportAccountsPage() {
  return <PortalItAdminPage accountMode="import" section="accounts" />;
}
