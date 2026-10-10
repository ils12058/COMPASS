"use client";

import { useState } from "react";
import { UserRoundSearch } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PortalWorkspaceNav } from "@/features/portal/components/portal-workspace-nav";
import {
  PORTAL_IT_ADMIN_AVAILABILITY_NAV_ITEMS,
  type PortalItAdminAvailabilitySection,
} from "@/features/portal/admin/availability/portal-it-admin-availability-navigation";
import { PortalItAdminEffectiveAvailability } from "@/features/portal/admin/availability/portal-it-admin-effective-availability";
import { PortalItAdminOfficeExceptions } from "@/features/portal/admin/availability/portal-it-admin-office-exceptions";
import { PortalItAdminOfficeSchedule } from "@/features/portal/admin/availability/portal-it-admin-office-schedule";
import { PortalItAdminProviderExceptions } from "@/features/portal/admin/availability/portal-it-admin-provider-exceptions";
import { PortalItAdminProviderSchedule } from "@/features/portal/admin/availability/portal-it-admin-provider-schedule";
import {
  AvailabilityEmptyState,
  AvailabilityListSkeleton,
  AvailabilityQueryError,
  availabilitySelectClassName,
} from "@/features/portal/admin/availability/portal-it-admin-availability-shared";
import {
  useOrganizationListEligiblePeople,
} from "@/lib/api/generated/organization/organization";
import {
  OrganizationListEligiblePeopleRole as OrganizationRoleValues,
} from "@/lib/api/generated/model";

const PROVIDER_SECTIONS: readonly PortalItAdminAvailabilitySection[] = [
  "provider-schedules",
  "provider-exceptions",
  "effective-availability",
];

export function PortalItAdminAvailabilityPage({
  canManage,
  section = "office-schedule",
}: {
  canManage: boolean;
  section?: PortalItAdminAvailabilitySection;
}) {
  const [providerSearch, setProviderSearch] = useState("");
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const needsProvider = PROVIDER_SECTIONS.includes(section);
  const providersQuery = useOrganizationListEligiblePeople(
    {
      page: 1,
      page_size: 50,
      role: OrganizationRoleValues.COUNSELOR,
      search: providerSearch || undefined,
    },
    {
      query: {
        enabled: canManage && needsProvider,
        retry: false,
        staleTime: 30_000,
      },
    },
  );
  const providers = providersQuery.data?.data.items ?? [];
  const providerId = providers.some((provider) => provider.id === selectedProviderId)
    ? selectedProviderId
    : providers[0]?.id ?? "";
  const providerName =
    providers.find((provider) => provider.id === providerId)?.display_name ?? "";

  let providerPicker = null;
  if (canManage) {
    if (providersQuery.isPending) {
      providerPicker = <AvailabilityListSkeleton label="Loading providers" />;
    } else if (providersQuery.isError) {
      providerPicker = (
        <AvailabilityQueryError
          message="We couldn’t load the counselor list for this availability view."
          onRetry={() => void providersQuery.refetch()}
        />
      );
    } else if (!providers.length) {
      providerPicker = (
        <AvailabilityEmptyState
          description={
            providerSearch
              ? "Try a different name or clear the search."
              : "Counselors will appear here once they are available for scheduling."
          }
          title={providerSearch ? "No matching counselors" : "No counselors found"}
        />
      );
    } else {
      providerPicker = (
        <div className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-6">
          <div className="flex items-start gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-support-soft)] text-[var(--compass-support-strong)]">
              <UserRoundSearch aria-hidden="true" className="size-5" />
            </span>
            <div className="min-w-0">
              <h2 className="font-heading text-xl font-bold tracking-tight">Choose a counselor</h2>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                Select the provider whose recurring hours or exceptions you want to review.
              </p>
            </div>
          </div>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="availability-provider-search">Search counselors</Label>
              <Input
                id="availability-provider-search"
                className="mt-2 h-10"
                placeholder="Name"
                value={providerSearch}
                onChange={(event) => setProviderSearch(event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="availability-provider">Counselor</Label>
              <select
                id="availability-provider"
                className={`${availabilitySelectClassName} mt-2`}
                value={providerId}
                onChange={(event) => setSelectedProviderId(event.target.value)}
              >
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.display_name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      );
    }
  }

  const content =
    section === "office-schedule" ? (
      <PortalItAdminOfficeSchedule canManage={canManage} />
    ) : section === "office-exceptions" ? (
      <PortalItAdminOfficeExceptions canManage={canManage} />
    ) : section === "provider-schedules" ? (
      <PortalItAdminProviderSchedule
        canManage={canManage}
        providerId={providerId}
        providerName={providerName}
      />
    ) : section === "provider-exceptions" ? (
      <PortalItAdminProviderExceptions
        canManage={canManage}
        providerId={providerId}
        providerName={providerName}
      />
    ) : (
      <PortalItAdminEffectiveAvailability
        canManage={canManage}
        providerId={providerId}
        providerName={providerName}
      />
    );

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
      <PortalWorkspaceNav
        activeValue={section}
        ariaLabel="Availability sections"
        items={PORTAL_IT_ADMIN_AVAILABILITY_NAV_ITEMS}
      />
      <div className="space-y-5">
        {needsProvider ? providerPicker : null}
        {content}
      </div>
    </div>
  );
}
