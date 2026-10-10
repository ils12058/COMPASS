import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Provider schedules",
};

export default function ItAdminProviderSchedulesPage() {
  return <PortalItAdminPage section="availability" availabilitySection="provider-schedules" />;
}
