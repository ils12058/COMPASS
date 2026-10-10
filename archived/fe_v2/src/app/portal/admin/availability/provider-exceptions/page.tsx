import type { Metadata } from "next";

import { PortalItAdminPage } from "@/features/portal/admin/portal-it-admin-page";

export const metadata: Metadata = {
  title: "Provider exceptions",
};

export default function ItAdminProviderExceptionsPage() {
  return <PortalItAdminPage section="availability" availabilitySection="provider-exceptions" />;
}
