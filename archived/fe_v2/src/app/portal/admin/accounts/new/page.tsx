import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Create account",
};

export default function ItAdminCreateAccountPage() {
  return <PortalItAdminPage accountMode="create" section="accounts" />;
}
