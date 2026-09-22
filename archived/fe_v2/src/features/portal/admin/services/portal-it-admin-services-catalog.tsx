"use client";

import Link from "next/link";
import { BriefcaseBusiness, ChevronLeft, ChevronRight, Plus, Search } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatAdminDate } from "@/features/portal/admin/portal-it-admin-shared";
import {
  AppointmentPolicy as AppointmentPolicyValues,
  type AppointmentPolicy,
  type ServiceResponse,
  type ServicesListParams,
} from "@/lib/api/generated/model";
import {
  useServicesList,
} from "@/lib/api/generated/services/services";
import {
  ServiceEmptyState,
  ServiceListSkeleton,
  ServiceQueryError,
  ServiceSection,
  ServiceStatusBadge,
  formatServiceValue,
  serviceSelectClassName,
} from "@/features/portal/admin/services/portal-it-admin-services-shared";

const PAGE_SIZE = 20;
type StatusFilter = "all" | "active" | "disabled";

function deliveryModesLabel(service: ServiceResponse) {
  return service.delivery_modes.length
    ? service.delivery_modes.map(formatServiceValue).join(" · ")
    : "Not set";
}

function providerRolesLabel(service: ServiceResponse) {
  return service.provider_roles.length
    ? service.provider_roles.map(formatServiceValue).join(" · ")
    : "Not assigned";
}

function ServiceTableRow({ service }: { service: ServiceResponse }) {
  return (
    <tr className="border-t border-[var(--compass-border)] align-top transition-colors hover:bg-[var(--compass-surface-subtle)]">
      <td className="px-4 py-4">
        <Link
          href={`/portal/admin/services/${service.id}`}
          className="block min-w-48 rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <span className="block font-semibold text-foreground">{service.name}</span>
          <span className="mt-1 block font-mono text-xs text-muted-foreground">
            {service.code}
          </span>
        </Link>
      </td>
      <td className="px-4 py-4">
        <ServiceStatusBadge active={service.is_active} />
      </td>
      <td className="px-4 py-4 text-sm text-muted-foreground">
        {formatServiceValue(service.appointment_policy)}
      </td>
      <td className="px-4 py-4 text-sm text-muted-foreground">
        <p>{deliveryModesLabel(service)}</p>
        <p className="mt-1 text-xs">{providerRolesLabel(service)}</p>
      </td>
      <td className="whitespace-nowrap px-4 py-4 text-sm text-muted-foreground">
        {formatAdminDate(service.updated_at)}
      </td>
    </tr>
  );
}

function ServiceMobileCard({ service }: { service: ServiceResponse }) {
  return (
    <Link
      href={`/portal/admin/services/${service.id}`}
      className="block rounded-2xl border border-[var(--compass-border)] bg-card p-4 shadow-sm outline-none transition-colors hover:bg-[var(--compass-surface-subtle)] focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="break-words font-semibold">{service.name}</p>
          <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
            {service.code}
          </p>
        </div>
        <ServiceStatusBadge active={service.is_active} />
      </div>
      <dl className="mt-4 grid gap-3 border-t border-[var(--compass-border)] pt-4 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted-foreground">
            Appointments
          </dt>
          <dd className="mt-1 font-medium">
            {formatServiceValue(service.appointment_policy)}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted-foreground">
            Delivery
          </dt>
          <dd className="mt-1 break-words text-muted-foreground">
            {deliveryModesLabel(service)}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted-foreground">
            Updated
          </dt>
          <dd className="mt-1 text-muted-foreground">
            {formatAdminDate(service.updated_at)}
          </dd>
        </div>
      </dl>
    </Link>
  );
}

export function PortalItAdminServicesCatalog({ canManage }: { canManage: boolean }) {
  const [draftSearch, setDraftSearch] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>(canManage ? "all" : "active");
  const [appointmentPolicy, setAppointmentPolicy] = useState<AppointmentPolicy | "">("");
  const [page, setPage] = useState(1);
  const params = useMemo<ServicesListParams>(
    () => ({
      appointment_policy: appointmentPolicy || undefined,
      include_inactive: canManage && status !== "active",
      page,
      page_size: PAGE_SIZE,
      search: search || undefined,
    }),
    [appointmentPolicy, canManage, page, search, status],
  );
  const servicesQuery = useServicesList(params, {
    query: {
      retry: false,
      staleTime: 30_000,
    },
  });
  const response = servicesQuery.data?.data;
  const services =
    response?.items.filter((service) => status !== "disabled" || !service.is_active) ?? [];

  function submitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setSearch(draftSearch.trim());
  }

  function clearFilters() {
    setDraftSearch("");
    setSearch("");
    setAppointmentPolicy("");
    setStatus(canManage ? "all" : "active");
    setPage(1);
  }

  return (
    <ServiceSection
      icon={BriefcaseBusiness}
      title="Service catalog"
      description="Manage the services people can request and the settings that shape how each one is delivered."
    >
      <div className="space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <form
            className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-end"
            onSubmit={submitFilters}
          >
            <div className="min-w-0 flex-1">
              <Label htmlFor="service-search">Search services</Label>
              <div className="relative mt-2">
                <Search
                  aria-hidden="true"
                  className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                />
                <Input
                  id="service-search"
                  className="h-10 pl-9"
                  placeholder="Name or code"
                  value={draftSearch}
                  onChange={(event) => setDraftSearch(event.target.value)}
                />
              </div>
            </div>
            <Button type="submit" className="h-10">
              <Search aria-hidden="true" />
              Search
            </Button>
          </form>
          <div className="flex flex-wrap gap-2 sm:justify-end">
            <select
              aria-label="Filter services by appointment policy"
              className={serviceSelectClassName}
              value={appointmentPolicy}
              onChange={(event) => {
                setAppointmentPolicy(event.target.value as AppointmentPolicy | "");
                setPage(1);
              }}
            >
              <option value="">All appointment policies</option>
              {Object.values(AppointmentPolicyValues).map((policy) => (
                <option key={policy} value={policy}>
                  {formatServiceValue(policy)}
                </option>
              ))}
            </select>
            {canManage ? (
              <select
                aria-label="Filter services by status"
                className={serviceSelectClassName}
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value as StatusFilter);
                  setPage(1);
                }}
              >
                <option value="all">All statuses</option>
                <option value="active">Active only</option>
                <option value="disabled">Disabled only</option>
              </select>
            ) : null}
            {canManage ? (
              <Button asChild type="button">
                <Link href="/portal/admin/services/new">
                  <Plus aria-hidden="true" />
                  Add service
                </Link>
              </Button>
            ) : null}
          </div>
        </div>

        {search || appointmentPolicy || (canManage && status !== "all") ? (
          <Button type="button" variant="ghost" onClick={clearFilters}>
            Clear filters
          </Button>
        ) : null}

        {servicesQuery.isPending ? (
          <ServiceListSkeleton />
        ) : servicesQuery.isError ? (
          <ServiceQueryError onRetry={() => void servicesQuery.refetch()} />
        ) : services.length ? (
          <>
            <div className="hidden overflow-x-auto rounded-2xl border border-[var(--compass-border)] md:block">
              <table className="w-full min-w-[50rem] text-left">
                <thead className="bg-[var(--compass-surface-subtle)] text-xs font-bold uppercase tracking-[0.1em] text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">Service</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Appointments</th>
                    <th className="px-4 py-3">Delivery and providers</th>
                    <th className="px-4 py-3">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {services.map((service) => (
                    <ServiceTableRow key={service.id} service={service} />
                  ))}
                </tbody>
              </table>
            </div>
            <div className="space-y-3 md:hidden">
              {services.map((service) => (
                <ServiceMobileCard key={service.id} service={service} />
              ))}
            </div>
          </>
        ) : (
          <ServiceEmptyState
            action={
              canManage ? (
                <Button asChild>
                  <Link href="/portal/admin/services/new">
                    <Plus aria-hidden="true" />
                    Add service
                  </Link>
                </Button>
              ) : undefined
            }
            description={
              search || appointmentPolicy || status === "disabled"
                ? "Try a different search or filter."
                : "Services will appear here once they are configured."
            }
            title={
              search || appointmentPolicy || status === "disabled"
                ? "No matching services"
                : "No services yet"
            }
          />
        )}

        {response ? (
          <div className="flex flex-col gap-3 border-t border-[var(--compass-border)] pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">Page {response.page}</p>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={page <= 1 || servicesQuery.isFetching}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                <ChevronLeft aria-hidden="true" />
                Previous
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={!response.has_next || servicesQuery.isFetching}
                onClick={() => setPage((current) => current + 1)}
              >
                Next
                <ChevronRight aria-hidden="true" />
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </ServiceSection>
  );
}
