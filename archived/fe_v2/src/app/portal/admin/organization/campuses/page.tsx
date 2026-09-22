import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Campuses",
};

export default function CampusesPage() {
  return <PortalItAdminPage section="organization" organizationSection="campuses" />;
}
