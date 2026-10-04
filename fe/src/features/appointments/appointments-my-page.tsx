"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Button, buttonVariants } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools } from "@/components/ui/floating-list-tools";
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
  AppointmentsUnavailable,
  appointmentErrorMessage,
  deliveryModeLabel,
  formatAppointmentDateTime,
  UPCOMING_APPOINTMENTS_VIEW,
  updateAppointmentQuery,
} from "@/features/appointments/appointments-shared";
import { getAppointmentAccess, type AppointmentAccess } from "@/features/appointments/appointments-access";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  AppointmentListOrdering,
  AppointmentStatus,
} from "@/lib/api/generated/model";
import { useAppointmentsListMy } from "@/lib/api/generated/appointments/appointments";

function isStatus(value: string | null): value is AppointmentStatus {
  return value !== null && Object.values(AppointmentStatus).includes(value as AppointmentStatus);
}

function isOrdering(value: string | null): value is AppointmentListOrdering {
  return value !== null && Object.values(AppointmentListOrdering).includes(value as AppointmentListOrdering);
}

function pageValue(value: string | null): number {
  const parsed = Number.parseInt(value ?? "1", 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

function MyAppointmentsList({ access }: { access: AppointmentAccess }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const statusParam = searchParams.get("status");
  const upcoming = statusParam === UPCOMING_APPOINTMENTS_VIEW;
  const status = isStatus(statusParam)
    ? statusParam
    : statusParam === "ALL" || upcoming
      ? undefined
      : AppointmentStatus.SCHEDULED;
  const fromDate = searchParams.get("from") ?? "";
  const toDate = searchParams.get("to") ?? "";
  const orderingParam = searchParams.get("ordering");
  const ordering = isOrdering(orderingParam)
    ? orderingParam
    : AppointmentListOrdering.START_ASC;
  const page = pageValue(searchParams.get("page"));

  const list = useAppointmentsListMy(
    {
      ...(status ? { status } : {}),
      ...(upcoming ? { upcoming: true } : {}),
      ...(fromDate ? { from_date: fromDate } : {}),
      ...(toDate ? { to_date: toDate } : {}),
      ordering,
      page,
      page_size: 20,
    },
    { query: { retry: false } },
  );

  function updateFilter(name: string, value: string) {
    router.replace(
      updateAppointmentQuery(
        pathname,
        new URLSearchParams(searchParams.toString()),
        { [name]: value },
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
  const filtering = Boolean(fromDate || toDate || (statusParam !== null && statusParam !== "ALL"));
  // Status and Order count only when they differ from the list's defaults.
  const filterCount = [
    status !== AppointmentStatus.SCHEDULED,
    fromDate,
    toDate,
    ordering !== AppointmentListOrdering.START_ASC,
  ].filter(Boolean).length;
  const clearHref = updateAppointmentQuery(
    pathname,
    new URLSearchParams(searchParams.toString()),
    { status: "ALL", from: "", to: "" },
  );

  return (
    <section aria-labelledby="my-appointments-heading">
      <AppointmentsLocalNavigation />
      <AppointmentsPageHeading
        headingId="my-appointments-heading"
        title="My appointments"
        description={
          access.isStudent
            ? "Shows scheduled appointments first. Use Filters to see past appointments."
            : undefined
        }
      />

      {/* No free-text search here, so each choice applies as soon as it changes. */}
      <FloatingListTools
        label="Appointment filters"
        filterCount={filterCount}
        clear={filtering ? (
          <Link href={clearHref} className={buttonVariants({ variant: "quiet" })}>
            Clear filters
          </Link>
        ) : undefined}
        filters={<>
        <FilterField label="Status" htmlFor="my-appointment-status">
          <Select
            id="my-appointment-status"
            value={upcoming ? UPCOMING_APPOINTMENTS_VIEW : status ?? "ALL"}
            onChange={(event) => updateFilter("status", event.target.value)}
          >
            <option value={AppointmentStatus.SCHEDULED}>Scheduled</option>
            <option value={UPCOMING_APPOINTMENTS_VIEW}>Upcoming (not yet started)</option>
            <option value="ALL">All statuses</option>
            <option value={AppointmentStatus.CANCELLED}>Cancelled</option>
            <option value={AppointmentStatus.COMPLETED}>Completed</option>
            <option value={AppointmentStatus.NO_SHOW}>No-show</option>
          </Select>
        </FilterField>
        <FilterField label="From date" htmlFor="my-appointment-from">
          <Input
            id="my-appointment-from"
            type="date"
            value={fromDate}
            onChange={(event) => updateFilter("from", event.target.value)}
          />
        </FilterField>
        <FilterField label="To date" htmlFor="my-appointment-to">
          <Input
            id="my-appointment-to"
            type="date"
            value={toDate}
            onChange={(event) => updateFilter("to", event.target.value)}
          />
        </FilterField>
        <FilterField label="Order" htmlFor="my-appointment-order">
          <Select
            id="my-appointment-order"
            value={ordering}
            onChange={(event) => updateFilter("ordering", event.target.value)}
          >
            <option value={AppointmentListOrdering.START_ASC}>Earliest start first</option>
            <option value={AppointmentListOrdering.START_DESC}>Latest start first</option>
          </Select>
        </FilterField>
        </>}
      />

      <Panel aria-labelledby="my-appointments-results-heading">
        <PanelHeader
          title="Appointments"
          titleId="my-appointments-results-heading"
          context={
            list.isFetching && !list.isPending
              ? "Refreshing Appointments…"
              : pageData && !list.isError
                ? describeResultPage({
                    count: items.length,
                    page: pageData.page,
                    hasNext: pageData.has_next,
                    noun: { one: "appointment", other: "appointments" },
                    filtered: filtering,
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
            action={
              <Button variant="secondary" onClick={() => void list.refetch()}>
                Retry
              </Button>
            }
          >
            {appointmentErrorMessage(list.error, "My Appointments could not be loaded.")}
          </PanelMessage>
        ) : items.length === 0 ? (
          <PanelMessage
            action={status !== undefined || upcoming || fromDate || toDate ? (
              <Link
                href={clearHref}
                className={buttonVariants({ variant: "secondary" })}
              >
                {filtering ? "Clear filters" : "Show all statuses"}
              </Link>
            ) : undefined}
          >
            {filtering
              ? "No appointments match the selected filters."
              : status === AppointmentStatus.SCHEDULED
                ? "No scheduled appointments match this view."
                : "No appointments are available."}
          </PanelMessage>
        ) : (
          <>
            <div className={`${dataTable.scroll} hidden md:block`}>
              <table className={`${dataTable.table} min-w-[760px]`}>
                <caption className="sr-only">My Appointments</caption>
                <thead className={dataTable.head}>
                  <tr>
                    <th scope="col" className={dataTable.headerCell}>{access.isStudent ? "Service" : "Student"}</th>
                    <th scope="col" className={dataTable.headerCell}>{access.isStudent ? "Counselor" : "Service"}</th>
                    <th scope="col" className={dataTable.headerCell}>Date and time</th>
                    <th scope="col" className={dataTable.headerCell}>Delivery</th>
                    <th scope="col" className={dataTable.headerCell}>Status</th>
                  </tr>
                </thead>
                <tbody className={dataTable.body}>
                  {items.map((appointment) => (
                    <tr key={appointment.id} className={dataTable.row}>
                      <th scope="row" className={`${dataTable.cell} font-normal`}>
                        <Link href={`/portal/appointments/${appointment.id}`} className="font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                          {access.isStudent ? appointment.service.name : appointment.student.display_name}
                        </Link>
                        <p className="mt-1 font-mono text-xs text-muted">{appointment.reference_code}</p>
                        {!access.isStudent && appointment.student.institutional_id ? (
                          <p className="mt-1 break-all text-xs text-muted">{appointment.student.institutional_id}</p>
                        ) : null}
                      </th>
                      <td className={`${dataTable.cell} text-ink`}>
                        {access.isStudent ? appointment.provider.display_name : appointment.service.name}
                      </td>
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
                        <Link href={`/portal/appointments/${appointment.id}`} className="break-words font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                          {access.isStudent ? appointment.service.name : appointment.student.display_name}
                        </Link>
                        <p className="mt-1 font-mono text-xs text-muted">{appointment.reference_code}</p>
                        {!access.isStudent && appointment.student.institutional_id ? (
                          <p className="mt-1 break-all text-xs text-muted">{appointment.student.institutional_id}</p>
                        ) : null}
                      </div>
                      <AppointmentStatusBadge status={appointment.status} />
                    </div>
                    <dl className="mt-3 grid gap-x-5 gap-y-2 text-sm sm:grid-cols-2">
                      <div>
                        <dt className="text-xs text-muted">{access.isStudent ? "Counselor" : "Service"}</dt>
                        <dd className="mt-0.5 text-ink">{access.isStudent ? appointment.provider.display_name : appointment.service.name}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted">Date and time</dt>
                        <dd className="mt-0.5 text-ink">{formatAppointmentDateTime(appointment.starts_at, appointment.ends_at)}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted">Delivery</dt>
                        <dd className="mt-0.5 text-ink">{deliveryModeLabel(appointment.delivery_mode)}</dd>
                      </div>
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

export function AppointmentsMyPage() {
  const { user } = usePortalSession();
  const access = getAppointmentAccess(user);
  if (!access.canViewSelf) return <AppointmentsUnavailable />;
  return <MyAppointmentsList access={access} />;
}
