"use client";

import { useAuthGetSession } from "@/lib/api/generated/auth/auth";
import { Button } from "@/components/ui/button";
import { PortalWorkspaceNav } from "@/features/portal/components/portal-workspace-nav";
import { SystemErrorPage } from "@/features/system/components/system-error-page";
import { getApiRequestReference } from "@/lib/api/request-reference";
import {
  PORTAL_IT_ADMIN_NAV_ITEMS,
  type PortalItAdminSection,
} from "@/features/portal/admin/portal-it-admin-navigation";
import type { PortalItAdminOrganizationSection } from "@/features/portal/admin/portal-it-admin-organization-navigation";
import { PortalItAdminOverview } from "@/features/portal/admin/portal-it-admin-overview";
import { PortalItAdminAccountsPage } from "@/features/portal/admin/accounts/portal-it-admin-accounts-page";
import { PortalItAdminAccountDetailPage } from "@/features/portal/admin/accounts/portal-it-admin-account-detail-page";
import { PortalItAdminAccountCreatePage } from "@/features/portal/admin/accounts/portal-it-admin-account-create-page";
import { PortalItAdminAccountImportPage } from "@/features/portal/admin/accounts/portal-it-admin-account-import-page";
import { PortalItAdminOrganizationPage } from "@/features/portal/admin/organization/portal-it-admin-organization-page";
import { PortalItAdminServicesPage } from "@/features/portal/admin/services/portal-it-admin-services-page";
import type { PortalItAdminAvailabilitySection } from "@/features/portal/admin/availability/portal-it-admin-availability-navigation";
import { PortalItAdminAvailabilityPage } from "@/features/portal/admin/availability/portal-it-admin-availability-page";

function PortalItAdminLoading() {
  return (
    <section className="space-y-6" aria-live="polite">
      <div className="space-y-3">
        <div className="h-4 w-28 animate-pulse rounded-full bg-muted" />
        <div className="h-12 w-72 animate-pulse rounded-2xl bg-muted" />
        <div className="h-5 w-full max-w-2xl animate-pulse rounded-xl bg-muted" />
      </div>
      <div className="grid gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <div className="h-24 animate-pulse rounded-3xl bg-card" />
        <div className="grid gap-5 xl:grid-cols-2">
          {Array.from({ length: 4 }, (_, index) => (
            <div
              key={index}
              className="h-56 animate-pulse rounded-3xl bg-card"
            />
          ))}
        </div>
      </div>
    </section>
  );
}

export function PortalItAdminPage({
  section = "overview",
  accountId,
  accountMode,
  organizationSection,
  serviceId,
  serviceMode,
  availabilitySection,
}: {
  accountMode?: "create" | "import";
  organizationSection?: PortalItAdminOrganizationSection;
  section?: PortalItAdminSection;
  accountId?: string;
  serviceId?: string;
  serviceMode?: "create";
  availabilitySection?: PortalItAdminAvailabilitySection;
}) {
  const sessionQuery = useAuthGetSession({
    query: {
      retry: false,
      staleTime: 30_000,
    },
  });
  const session = sessionQuery.data?.data;

  if (sessionQuery.isPending) {
    return <PortalItAdminLoading />;
  }

  if (sessionQuery.isError || !session) {
    return (
      <SystemErrorPage
        code="IT Admin unavailable"
        title="We couldn’t open platform operations."
        description="Please try again. If the problem continues, return to COMPASS and open the workspace again."
        requestReference={getApiRequestReference(sessionQuery.error)}
        primaryAction={
          <Button onClick={() => void sessionQuery.refetch()}>Try again</Button>
        }
      />
    );
  }

  const capabilities = session.user.capabilities ?? [];
  const requiredCapabilities =
    section === "accounts"
      ? ["accounts.view", "accounts.manage"]
    : section === "organization"
        ? organizationSection === "assignments"
          ? ["organization.manage"]
          : ["organization.view"]
        : section === "services"
          ? ["services.view", "services.manage"]
          : section === "availability"
            ? ["availability.view", "availability.manage"]
          : ["platform_operations.view", "platform_operations.manage"];
  const hasRequiredCapability = capabilities.some((capability) =>
    requiredCapabilities.includes(capability),
  );

  if (!hasRequiredCapability) {
    return (
      <SystemErrorPage
        code="Access restricted"
        title="This area isn’t available to your account."
        description="This area is limited to authorized IT Admin staff."
        secondaryHref="/portal"
        secondaryLabel="Back to workspace"
      />
    );
  }

  const accountHeading = accountId
    ? "Account details"
    : accountMode === "create"
      ? "Create account"
      : accountMode === "import"
        ? "Import accounts"
        : "Accounts";
  const accountDescription = accountId
    ? "Review this account’s identity, access, and sign-in protections."
    : accountMode === "create"
      ? "Add one managed account with its institutional identity and primary role."
      : accountMode === "import"
        ? "Validate a bounded CSV first, then commit it only after the row results are ready."
        : "Find an account and review the access and sign-in settings attached to it.";
  const organizationHeading =
    organizationSection === "campuses"
      ? "Campuses"
      : organizationSection === "colleges"
        ? "Colleges"
        : organizationSection === "programs"
          ? "Programs"
          : organizationSection === "assignments"
            ? "Assignments"
          : "Organization";
  const organizationDescription =
    organizationSection === "campuses"
      ? "Maintain the campus records that anchor the university structure."
      : organizationSection === "colleges"
        ? "Maintain colleges and the campus each one belongs to."
        : organizationSection === "programs"
          ? "Maintain programs and the college that offers each one."
          : organizationSection === "assignments"
            ? "Connect colleges, staff, counselors, and students through the operational relationships they use."
          : "Keep campuses, colleges, and programs aligned for the workflows that depend on them.";
  const serviceHeading = serviceId
    ? "Service details"
    : serviceMode === "create"
      ? "Create service"
      : "Services";
  const serviceDescription = serviceId
    ? "Review the service settings and how this option can be delivered."
    : serviceMode === "create"
      ? "Add a service to the catalog and set the options staff will use when offering it."
      : "Manage the services people can request and the settings that shape how each one is delivered.";
  const availabilityHeading =
    availabilitySection === "office-exceptions"
      ? "Office exceptions"
      : availabilitySection === "provider-schedules"
        ? "Provider schedules"
        : availabilitySection === "provider-exceptions"
          ? "Provider exceptions"
          : availabilitySection === "effective-availability"
            ? "Effective availability"
            : "Availability";
  const availabilityDescription =
    availabilitySection === "office-exceptions"
      ? "Record office closures or temporary changes that override the recurring schedule."
      : availabilitySection === "provider-schedules"
        ? "Set recurring availability for counselor providers."
        : availabilitySection === "provider-exceptions"
          ? "Record temporary unavailability for counselor providers."
          : availabilitySection === "effective-availability"
            ? "Preview the hours when a provider and the office overlap for a service."
            : "Set the recurring hours that guide office and provider availability.";

  return (
    <section aria-labelledby="portal-it-admin-heading" className="space-y-7">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--compass-brand-gold)]">
          IT Admin
        </p>
        <h1
          id="portal-it-admin-heading"
          className="mt-2 font-heading text-4xl font-bold tracking-tight"
        >
          {section === "accounts"
            ? accountHeading
            : section === "organization"
              ? organizationHeading
              : section === "services"
                ? serviceHeading
                : section === "availability"
                  ? availabilityHeading
                  : "Platform overview"}
        </h1>
        <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">
          {section === "accounts"
            ? accountDescription
            : section === "organization"
              ? organizationDescription
              : section === "services"
                ? serviceDescription
                : section === "availability"
                  ? availabilityDescription
                  : "Keep an eye on platform health, maintenance, delivery, and recent technical activity."}
        </p>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <PortalWorkspaceNav
          activeValue={section}
          ariaLabel="IT Admin sections"
          items={PORTAL_IT_ADMIN_NAV_ITEMS}
        />
        {section === "accounts" ? (
          accountId ? (
            <PortalItAdminAccountDetailPage userId={accountId} />
          ) : accountMode === "create" ? (
            <PortalItAdminAccountCreatePage />
          ) : accountMode === "import" ? (
            <PortalItAdminAccountImportPage />
          ) : (
            <PortalItAdminAccountsPage />
          )
        ) : section === "organization" ? (
          <PortalItAdminOrganizationPage
            canManage={capabilities.includes("organization.manage")}
            section={organizationSection}
          />
        ) : section === "services" ? (
          <PortalItAdminServicesPage
            canManage={capabilities.includes("services.manage")}
            mode={serviceMode}
            serviceId={serviceId}
          />
        ) : section === "availability" ? (
          <PortalItAdminAvailabilityPage
            canManage={capabilities.includes("availability.manage")}
            section={availabilitySection}
          />
        ) : (
          <PortalItAdminOverview />
        )}
      </div>
    </section>
  );
}
