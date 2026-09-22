import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Services",
};

export default function ItAdminServicesPage() {
  return <PortalItAdminPage section="services" />;
}
