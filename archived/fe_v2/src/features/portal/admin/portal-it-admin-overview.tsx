import { PortalItAdminActivityCard } from "@/features/portal/admin/portal-it-admin-activity-card";
import { PortalItAdminEmailCard } from "@/features/portal/admin/portal-it-admin-email-card";
import { PortalItAdminHealthCard } from "@/features/portal/admin/portal-it-admin-health-card";
import { PortalItAdminMaintenanceCard } from "@/features/portal/admin/portal-it-admin-maintenance-card";
import { PortalItAdminMetadataCard } from "@/features/portal/admin/portal-it-admin-metadata-card";

export function PortalItAdminOverview() {
  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-2">
        <PortalItAdminHealthCard />
        <PortalItAdminMaintenanceCard />
      </div>
      <PortalItAdminEmailCard />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(18rem,0.65fr)]">
        <PortalItAdminActivityCard />
        <PortalItAdminMetadataCard />
      </div>
    </div>
  );
}
