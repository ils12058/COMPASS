import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Effective availability",
};

export default function ItAdminEffectiveAvailabilityPage() {
  return <PortalItAdminPage section="availability" availabilitySection="effective-availability" />;
}
