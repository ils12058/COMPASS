import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Programs",
};

export default function ProgramsPage() {
  return <PortalItAdminPage section="organization" organizationSection="programs" />;
}
