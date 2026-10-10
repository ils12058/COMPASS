import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "IT Admin",
};

export default function ItAdminPage() {
  return <PortalItAdminPage />;
}
