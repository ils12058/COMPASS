import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Assignments",
};

export default function AssignmentsPage() {
  return <PortalItAdminPage section="organization" organizationSection="assignments" />;
}
