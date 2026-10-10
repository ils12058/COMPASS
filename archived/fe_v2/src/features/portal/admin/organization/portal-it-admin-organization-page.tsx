"use client";

import { PortalWorkspaceNav } from "@/features/portal/components/portal-workspace-nav";
import {
  PORTAL_IT_ADMIN_ORGANIZATION_NAV_ITEMS,
  type PortalItAdminOrganizationSection,
} from "@/features/portal/admin/portal-it-admin-organization-navigation";
import { PortalItAdminOrganizationCampuses } from "@/features/portal/admin/organization/portal-it-admin-organization-campuses";
import { PortalItAdminOrganizationColleges } from "@/features/portal/admin/organization/portal-it-admin-organization-colleges";
import { PortalItAdminOrganizationOverview } from "@/features/portal/admin/organization/portal-it-admin-organization-overview";
import { PortalItAdminOrganizationPrograms } from "@/features/portal/admin/organization/portal-it-admin-organization-programs";
import { PortalItAdminOrganizationAssignmentsPage } from "@/features/portal/admin/organization/assignments/portal-it-admin-organization-assignments-page";

export function PortalItAdminOrganizationPage({
  canManage,
  section = "overview",
}: {
  canManage: boolean;
  section?: PortalItAdminOrganizationSection;
}) {
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
      <PortalWorkspaceNav
        activeValue={section}
        ariaLabel="Organization sections"
        items={PORTAL_IT_ADMIN_ORGANIZATION_NAV_ITEMS}
      />
      {section === "campuses" ? (
        <PortalItAdminOrganizationCampuses canManage={canManage} />
      ) : section === "colleges" ? (
        <PortalItAdminOrganizationColleges canManage={canManage} />
      ) : section === "programs" ? (
        <PortalItAdminOrganizationPrograms canManage={canManage} />
      ) : section === "assignments" ? (
        <PortalItAdminOrganizationAssignmentsPage />
      ) : (
        <PortalItAdminOrganizationOverview />
      )}
    </div>
  );
}
