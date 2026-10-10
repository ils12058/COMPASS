import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Colleges",
};

export default function CollegesPage() {
  return <PortalItAdminPage section="organization" organizationSection="colleges" />;
}
