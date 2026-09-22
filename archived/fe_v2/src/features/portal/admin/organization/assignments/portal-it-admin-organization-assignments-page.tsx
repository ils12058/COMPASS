"use client";

import { useState } from "react";
import { GitBranch } from "lucide-react";

import { PortalWorkspaceNav } from "@/features/portal/components/portal-workspace-nav";
import {
  PORTAL_IT_ADMIN_ORGANIZATION_NAV_ITEMS,
} from "@/features/portal/admin/portal-it-admin-organization-navigation";
import { PortalItAdminOrganizationCounselorResponsibilities } from "@/features/portal/admin/organization/assignments/portal-it-admin-organization-counselor-responsibilities";
import {
  AssignmentTabs,
  type PortalItAdminAssignmentTab,
} from "@/features/portal/admin/organization/assignments/portal-it-admin-organization-assignment-shared";
import { PortalItAdminOrganizationStaffSupervision } from "@/features/portal/admin/organization/assignments/portal-it-admin-organization-staff-supervision";
import { PortalItAdminOrganizationStudentAffiliations } from "@/features/portal/admin/organization/assignments/portal-it-admin-organization-student-affiliations";

export function PortalItAdminOrganizationAssignmentsPage() {
  const [activeTab, setActiveTab] = useState<PortalItAdminAssignmentTab>(
    "counselor-responsibilities",
  );

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
      <PortalWorkspaceNav
        activeValue="assignments"
        ariaLabel="Organization sections"
        items={PORTAL_IT_ADMIN_ORGANIZATION_NAV_ITEMS}
      />
      <div className="space-y-5">
        <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
          <div className="flex items-start gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-support-soft)] text-[var(--compass-support-strong)]">
              <GitBranch aria-hidden="true" className="size-5" />
            </span>
            <div>
              <h2 className="font-heading text-2xl font-bold tracking-tight">Assignments</h2>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
                Keep the relationships that guide responsibility routing in one place. Choose an area below to review or update it.
              </p>
            </div>
          </div>
          <div className="mt-6">
            <AssignmentTabs activeTab={activeTab} onChange={setActiveTab} />
          </div>
        </section>

        {activeTab === "counselor-responsibilities" ? (
          <PortalItAdminOrganizationCounselorResponsibilities />
        ) : activeTab === "staff-supervision" ? (
          <PortalItAdminOrganizationStaffSupervision />
        ) : (
          <PortalItAdminOrganizationStudentAffiliations />
        )}
      </div>
    </div>
  );
}
