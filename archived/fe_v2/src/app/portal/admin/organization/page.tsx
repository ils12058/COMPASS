import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Organization",
};

export default function OrganizationPage() {
  return <PortalItAdminPage section="organization" organizationSection="overview" />;
}
