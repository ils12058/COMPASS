"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FilterField, FilterToolbar } from "@/components/ui/filter-toolbar";
import { Input } from "@/components/ui/input";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import {
  AppointmentListSkeleton,
  AppointmentStatusBadge,
  AppointmentsLocalNavigation,
  AppointmentsPageHeading,
  appointmentErrorMessage,
  appointmentStatusLabel,
  deliveryModeLabel,
  formatAppointmentDateTime,
  UPCOMING_APPOINTMENTS_VIEW,
  updateAppointmentQuery,
} from "@/features/appointments/appointments-shared";
import { AppointmentsUnavailable } from "@/features/appointments/appointments-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  AppointmentListOrdering,
  AppointmentStatus,
  DeliveryMode,
} from "@/lib/api/generated/model";
import { useAppointmentsListManaged } from "@/lib/api/generated/appointments/appointments";
import { useServicesList } from "@/lib/api/generated/services/services";

function isStatus(value: string | null): value is AppointmentStatus {
  return value !== null && Object.values(AppointmentStatus).includes(value as AppointmentStatus);
}

function isDeliveryMode(value: string | null): value is DeliveryMode {
  return value !== null && Object.values(DeliveryMode).includes(value as DeliveryMode);
}

function isOrdering(value: string | null): value is AppointmentListOrdering {
  return value !== null && Object.values(AppointmentListOrdering).includes(value as AppointmentListOrdering);
}

const UUID_PATTERN = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;

function pageValue(value: string | null): number {
  const parsed = Number.parseInt(value ?? "1", 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

type ManagedFilters = {
  search: string;
  service: string;
  status: string;
  mode: string;
  from: string;
  to: string;
  ordering: string;
};

// Search and filters apply together through one Apply action. The parent remounts this form when
// the URL changes, so the fields always start from the applied filters.
function ManagedAppointmentFilters({
  applied,
  hasFilters,
  canFilterService,
  serviceOptions,
  servicesPending,
  servicesFailed,
  onApply,
  onClear,
}: {
  applied: ManagedFilters;
  hasFilters: boolean;
  canFilterService: boolean;
  serviceOptions: { id: string; name: string }[];
  servicesPending: boolean;
  servicesFailed: boolean;
  onApply: (filters: ManagedFilters) => void;
  onClear: () => void;
}) {
  const [draft, setDraft] = useState(applied);
  const appliedServiceKnown = serviceOptions.some((service) => service.id === applied.service);

  function set(name: keyof ManagedFilters, value: string) {
    setDraft((current) => ({ ...current, [name]: value }));
  }

  return (
    <form
      role="search"
      aria-label="Managed appointments"
      className="mb-5"
      onSubmit={(event) => {
        event.preventDefault();
        onApply({ ...draft, search: draft.search.trim() });
      }}
    >
      <FilterToolbar
        fieldsClassName="lg:grid-cols-3"
        actions={
          <>
            {hasFilters ? (
              <Button variant="quiet" onClick={onClear}>
                Clear filters
              </Button>
            ) : null}
            <Button type="submit">Apply filters</Button>
          </>
        }
      >
        <FilterField label="Search" htmlFor="managed-appointment-search" className="sm:col-span-2 lg:col-span-1">
          <Input
            id="managed-appointment-search"
            type="search"
            value={draft.search}
            onChange={(event) => set("search", event.target.value)}
            placeholder="Search by reference, Student name, or Institutional ID"
          />
        </FilterField>
        {canFilterService ? (
          <FilterField
            label="Service"
            htmlFor="managed-appointment-service"
            hint={servicesFailed ? (
              <p id="managed-appointment-service-error" className="text-xs text-warning">Service choices could not be loaded.</p>
            ) : null}
          >
            <Select
              id="managed-appointment-service"
              value={draft.service}
              disabled={servicesPending && !applied.service}
              aria-describedby={servicesFailed ? "managed-appointment-service-error" : undefined}
              onChange={(event) => set("service", event.target.value)}
            >
              <option value="">All Services</option>
              {applied.service && !appliedServiceKnown ? (
                <option value={applied.service}>
                  {servicesPending ? "Loading Service…" : "Selected Service"}
                </option>
              ) : null}
              {serviceOptions.map((service) => (
                <option key={service.id} value={service.id}>{service.name}</option>
              ))}
            </Select>
          </FilterField>
        ) : null}
        <FilterField label="Status" htmlFor="managed-appointment-status">
          <Select id="managed-appointment-status" value={draft.status} onChange={(event) => set("status", event.target.value)}>
            <option value={AppointmentStatus.SCHEDULED}>{appointmentStatusLabel(AppointmentStatus.SCHEDULED)}</option>
            <option value={UPCOMING_APPOINTMENTS_VIEW}>Upcoming (not yet started)</option>
            <option value="ALL">All statuses</option>
            <option value={AppointmentStatus.CANCELLED}>{appointmentStatusLabel(AppointmentStatus.CANCELLED)}</option>
            <option value={AppointmentStatus.COMPLETED}>{appointmentStatusLabel(AppointmentStatus.COMPLETED)}</option>
            <option value={AppointmentStatus.NO_SHOW}>{appointmentStatusLabel(AppointmentStatus.NO_SHOW)}</option>
          </Select>
        </FilterField>
        <FilterField label="Delivery" htmlFor="managed-appointment-mode">
          <Select id="managed-appointment-mode" value={draft.mode} onChange={(event) => set("mode", event.target.value)}>
            <option value="">All modes</option>
            <option value={DeliveryMode.IN_PERSON}>In person</option>
            <option value={DeliveryMode.ONLINE}>Online</option>
          </Select>
        </FilterField>
        <FilterField label="From" htmlFor="managed-appointment-from">
          <Input id="managed-appointment-from" type="date" value={draft.from} onChange={(event) => set("from", event.target.value)} />
        </FilterField>
        <FilterField label="To" htmlFor="managed-appointment-to">
          <Input id="managed-appointment-to" type="date" value={draft.to} onChange={(event) => set("to", event.target.value)} />
        </FilterField>
        <FilterField label="Order" htmlFor="managed-appointment-order">
          <Select id="managed-appointment-order" value={draft.ordering} onChange={(event) => set("ordering", event.target.value)}>
            <option value={AppointmentListOrdering.START_ASC}>Earliest start first</option>
            <option value={AppointmentListOrdering.START_DESC}>Latest start first</option>
          </Select>
        </FilterField>
      </FilterToolbar>
    </form>
  );
}

function ManagedAppointmentsList() {
  const { user } = usePortalSession();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const search = (searchParams.get("search") ?? "").trim();
  const statusParam = searchParams.get("status");
  const upcoming = statusParam === UPCOMING_APPOINTMENTS_VIEW;
  const status = isStatus(statusParam)
    ? statusParam
    : statusParam === "ALL" || upcoming
      ? undefined
      : AppointmentStatus.SCHEDULED;
  const modeParam = searchParams.get("mode");
  const mode = isDeliveryMode(modeParam) ? modeParam : undefined;
  const fromDate = searchParams.get("from") ?? "";
  const toDate = searchParams.get("to") ?? "";
  const orderingParam = searchParams.get("ordering");
  const ordering = isOrdering(orderingParam)
    ? orderingParam
    : AppointmentListOrdering.START_ASC;
  const page = pageValue(searchParams.get("page"));
  // Service choices come from the Service Catalog, which every Appointment
  // manager can read; the list shows Service names, never identifiers.
  const canFilterService = user.capabilities.includes("services.catalog.view");
  const serviceParam = searchParams.get("service") ?? "";
  const serviceId = canFilterService && UUID_PATTERN.test(serviceParam) ? serviceParam : undefined;
  const services = useServicesList(
    { page: 1, page_size: 50 },
    { query: { enabled: canFilterService, retry: false, staleTime: 5 * 60_000 } },
  );
  const serviceOptions = services.data?.data.items ?? [];

  const list = useAppointmentsListManaged(
    {
      ...(search ? { search } : {}),
      ...(serviceId ? { service_id: serviceId } : {}),
      ...(status ? { status } : {}),
      ...(upcoming ? { upcoming: true } : {}),
      ...(mode ? { delivery_mode: mode } : {}),
      ...(fromDate ? { from_date: fromDate } : {}),
      ...(toDate ? { to_date: toDate } : {}),
      ordering,
      page,
      page_size: 20,
    },
    { query: { retry: false } },
  );

  function applyFilters(next: ManagedFilters) {
    router.replace(
      updateAppointmentQuery(
        pathname,
        new URLSearchParams(searchParams.toString()),
        {
          search: next.search,
          service: canFilterService ? next.service : "",
          status: next.status,
          mode: next.mode,
          from: next.from,
          to: next.to,
          ordering: next.ordering,
        },
      ),
      { scroll: false },
    );
  }

  function movePage(nextPage: number) {
    router.push(
      updateAppointmentQuery(
        pathname,
        new URLSearchParams(searchParams.toString()),
        { page: String(nextPage) },
        false,
      ),
      { scroll: false },
    );
  }

  const pageData = list.data?.data;
  const items = pageData?.items ?? [];
  const hasFilters = Boolean(search || serviceId || mode || fromDate || toDate || (statusParam !== null && statusParam !== "ALL"));

  return (
    <section aria-labelledby="manage-appointments-heading">
      <AppointmentsLocalNavigation />
      <AppointmentsPageHeading
        headingId="manage-appointments-heading"
        title="Manage appointments"
        description="Review appointments assigned to the areas you manage."
      />

      <ManagedAppointmentFilters
        key={searchParams.toString()}
        applied={{
          search,
          service: serviceId ?? "",
          status: upcoming ? UPCOMING_APPOINTMENTS_VIEW : status ?? "ALL",
          mode: mode ?? "",
          from: fromDate,
          to: toDate,
          ordering,
        }}
        hasFilters={hasFilters}
        canFilterService={canFilterService}
        serviceOptions={serviceOptions}
        servicesPending={services.isPending}
        servicesFailed={services.isError}
        onApply={applyFilters}
        onClear={() => router.replace(
          updateAppointmentQuery(
            pathname,
            new URLSearchParams(searchParams.toString()),
            { search: "", service: "", status: "ALL", mode: "", from: "", to: "" },
          ),
          { scroll: false },
        )}
      />

      <Panel aria-labelledby="managed-appointments-results-heading">
        <PanelHeader
          title="Appointments"
          titleId="managed-appointments-results-heading"
          context={
            list.isFetching && !list.isPending
              ? "Refreshing Appointments…"
              : pageData && !list.isError
                ? describeResultPage({
                    count: items.length,
                    page: pageData.page,
                    hasNext: pageData.has_next,
                    noun: { one: "appointment", other: "appointments" },
                    filtered: hasFilters,
                  })
                : null
          }
        />
        {list.isPending ? (
          <AppointmentListSkeleton framed={false} />
        ) : list.isError ? (
          <PanelMessage
            role="alert"
            tone="danger"
            action={<Button variant="secondary" onClick={() => void list.refetch()}>Retry</Button>}
          >
            {appointmentErrorMessage(list.error, "Managed appointments could not be loaded.")}
          </PanelMessage>
        ) : items.length === 0 ? (
          <PanelMessage
            action={hasFilters || status !== undefined ? (
              <Link
                href={updateAppointmentQuery(
                  pathname,
                  new URLSearchParams(searchParams.toString()),
                  { search: "", service: "", status: "ALL", mode: "", from: "", to: "" },
                )}
                className={buttonVariants({ variant: "secondary" })}
              >
                {hasFilters ? "Clear filters" : "Show all statuses"}
              </Link>
            ) : undefined}
          >
            {hasFilters
              ? "No appointments match the selected filters."
              : status === AppointmentStatus.SCHEDULED
                ? "No scheduled appointments are available."
                : "No appointments are available."}
          </PanelMessage>
        ) : (
          <>
            <div className={`${dataTable.scroll} hidden md:block`}>
              <table className={`${dataTable.table} min-w-[1000px]`}>
                <caption className="sr-only">Managed appointments</caption>
                <thead className={dataTable.head}>
                  <tr>
                    <th scope="col" className={dataTable.headerCell}>Appointment</th>
                    <th scope="col" className={dataTable.headerCell}>Student</th>
                    <th scope="col" className={dataTable.headerCell}>Service</th>
                    <th scope="col" className={dataTable.headerCell}>Counselor</th>
                    <th scope="col" className={dataTable.headerCell}>Date and time</th>
                    <th scope="col" className={dataTable.headerCell}>Delivery</th>
                    <th scope="col" className={dataTable.headerCell}>Status</th>
                  </tr>
                </thead>
                <tbody className={dataTable.body}>
                  {items.map((appointment) => (
                    <tr key={appointment.id} className={dataTable.row}>
                      <th scope="row" className={`${dataTable.cell} font-normal`}>
                        <Link href={`/portal/appointments/${appointment.id}`} className="font-mono text-xs font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{appointment.reference_code}</Link>
                      </th>
                      <td className={dataTable.cell}>
                        <p className="font-medium text-ink">{appointment.student.display_name}</p>
                        {appointment.student.institutional_id ? <p className="mt-1 break-all text-xs text-muted">{appointment.student.institutional_id}</p> : null}
                      </td>
                      <td className={`${dataTable.cell} text-ink`}>{appointment.service.name}</td>
                      <td className={`${dataTable.cell} text-ink`}>{appointment.provider.display_name}</td>
                      <td className={`${dataTable.cell} text-ink`}>{formatAppointmentDateTime(appointment.starts_at, appointment.ends_at)}</td>
                      <td className={`${dataTable.cell} text-ink`}>{deliveryModeLabel(appointment.delivery_mode)}</td>
                      <td className={dataTable.cell}><AppointmentStatusBadge status={appointment.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="divide-y divide-border md:hidden">
              {items.map((appointment) => (
                <li key={appointment.id} className="px-4 py-4">
                  <article>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <Link href={`/portal/appointments/${appointment.id}`} className="break-all font-mono text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{appointment.reference_code}</Link>
                        <p className="mt-1 break-words font-medium text-ink">{appointment.student.display_name}</p>
                        {appointment.student.institutional_id ? <p className="mt-1 break-all text-xs text-muted">{appointment.student.institutional_id}</p> : null}
                      </div>
                      <AppointmentStatusBadge status={appointment.status} />
                    </div>
                    <dl className="mt-3 grid gap-x-5 gap-y-2 text-sm sm:grid-cols-2">
                      <div><dt className="text-xs text-muted">Service</dt><dd className="mt-0.5 text-ink">{appointment.service.name}</dd></div>
                      <div><dt className="text-xs text-muted">Counselor</dt><dd className="mt-0.5 text-ink">{appointment.provider.display_name}</dd></div>
                      <div><dt className="text-xs text-muted">Date and time</dt><dd className="mt-0.5 text-ink">{formatAppointmentDateTime(appointment.starts_at, appointment.ends_at)}</dd></div>
                      <div><dt className="text-xs text-muted">Delivery</dt><dd className="mt-0.5 text-ink">{deliveryModeLabel(appointment.delivery_mode)}</dd></div>
                    </dl>
                  </article>
                </li>
              ))}
            </ul>
          </>
        )}
        {!list.isPending && !list.isError ? (
          <CanonicalPagination
            className="border-brand-line px-4 py-3 sm:px-5"
            page={pageData?.page ?? page}
            hasNext={pageData?.has_next ?? false}
            label="Appointment pages"
            onPageChange={movePage}
          />
        ) : null}
      </Panel>
    </section>
  );
}

export function AppointmentsManagedPage() {
  const { user } = usePortalSession();
  if (!user.capabilities.includes("appointments.manage")) {
    return (
      <AppointmentsUnavailable>
        Appointment management is unavailable to this account.
      </AppointmentsUnavailable>
    );
  }
  return <ManagedAppointmentsList />;
}
