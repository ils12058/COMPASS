import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Create service",
};

export default function ItAdminCreateServicePage() {
  return <PortalItAdminPage section="services" serviceMode="create" />;
}
