"use client";

import { PortalWorkspaceNav } from "@/features/portal/components/portal-workspace-nav";
import {
  PORTAL_IT_ADMIN_SERVICES_NAV_ITEMS,
  type PortalItAdminServicesSection,
} from "@/features/portal/admin/services/portal-it-admin-services-navigation";
import { PortalItAdminServiceCreatePage } from "@/features/portal/admin/services/portal-it-admin-service-create-page";
import { PortalItAdminServiceDetailPage } from "@/features/portal/admin/services/portal-it-admin-service-detail-page";
import { PortalItAdminServicesCatalog } from "@/features/portal/admin/services/portal-it-admin-services-catalog";

export function PortalItAdminServicesPage({
  canManage,
  mode,
  section = "catalog",
  serviceId,
}: {
  canManage: boolean;
  mode?: "create";
  section?: PortalItAdminServicesSection;
  serviceId?: string;
}) {
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
      <PortalWorkspaceNav
        activeValue={section}
        ariaLabel="Services sections"
        items={PORTAL_IT_ADMIN_SERVICES_NAV_ITEMS}
      />
      {mode === "create" ? (
        <PortalItAdminServiceCreatePage />
      ) : serviceId ? (
        <PortalItAdminServiceDetailPage canManage={canManage} serviceId={serviceId} />
      ) : (
        <PortalItAdminServicesCatalog canManage={canManage} />
      )}
    </div>
  );
}
