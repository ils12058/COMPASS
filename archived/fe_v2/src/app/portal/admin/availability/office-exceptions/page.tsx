import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Office exceptions",
};

export default function ItAdminOfficeExceptionsPage() {
  return <PortalItAdminPage section="availability" availabilitySection="office-exceptions" />;
}
