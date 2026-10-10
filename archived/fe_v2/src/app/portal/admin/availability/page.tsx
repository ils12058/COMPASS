import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Availability",
};

export default function ItAdminAvailabilityPage() {
  return <PortalItAdminPage section="availability" availabilitySection="office-schedule" />;
}
