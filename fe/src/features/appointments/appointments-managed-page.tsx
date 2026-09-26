"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AppointmentStatusBadge,
  AppointmentsLocalNavigation,
  AppointmentsPageHeading,
  PaginationControls,
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

const controlClass = "min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

function isStatus(value: string | null): value is AppointmentStatus {
  return value !== null && Object.values(AppointmentStatus).includes(value as AppointmentStatus);
}

function isDeliveryMode(value: string | null): value is DeliveryMode {
  return value !== null && Object.values(DeliveryMode).includes(value as DeliveryMode);
}

function isOrdering(value: string | null): value is AppointmentListOrdering {
  return value !== null && Object.values(AppointmentListOrdering).includes(value as AppointmentListOrdering);
}

function pageValue(value: string | null): number {
  const parsed = Number.parseInt(value ?? "1", 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

function ManagedAppointmentsList() {
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

  const list = useAppointmentsListManaged(
    {
      ...(search ? { search } : {}),
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

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    updateFilter("search", String(form.get("search") ?? "").trim());
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
  const hasFilters = Boolean(search || mode || fromDate || toDate || (statusParam !== null && statusParam !== "ALL"));

  return (
    <section aria-labelledby="manage-appointments-heading">
      <AppointmentsLocalNavigation />
      <AppointmentsPageHeading
        headingId="manage-appointments-heading"
        title="Manage appointments"
        description="Appointments within your authorized operational scope."
      />

      <div className="border-y border-border py-5">
        <form onSubmit={submitSearch} className="grid gap-4 lg:grid-cols-[minmax(16rem,2fr)_repeat(5,minmax(9rem,1fr))_auto] lg:items-end">
          <div className="grid gap-2">
            <Label htmlFor="managed-appointment-search">Search</Label>
            <Input
              key={search}
              id="managed-appointment-search"
              name="search"
              type="search"
              defaultValue={search}
              placeholder="Search by reference, Student name, or Institutional ID"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="managed-appointment-status">Status</Label>
            <select id="managed-appointment-status" className={controlClass} value={upcoming ? UPCOMING_APPOINTMENTS_VIEW : status ?? "ALL"} onChange={(event) => updateFilter("status", event.target.value)}>
              <option value={AppointmentStatus.SCHEDULED}>{appointmentStatusLabel(AppointmentStatus.SCHEDULED)}</option>
              <option value={UPCOMING_APPOINTMENTS_VIEW}>Upcoming (not yet started)</option>
              <option value="ALL">All statuses</option>
              <option value={AppointmentStatus.CANCELLED}>{appointmentStatusLabel(AppointmentStatus.CANCELLED)}</option>
              <option value={AppointmentStatus.COMPLETED}>{appointmentStatusLabel(AppointmentStatus.COMPLETED)}</option>
              <option value={AppointmentStatus.NO_SHOW}>{appointmentStatusLabel(AppointmentStatus.NO_SHOW)}</option>
            </select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="managed-appointment-mode">Delivery</Label>
            <select id="managed-appointment-mode" className={controlClass} value={mode ?? ""} onChange={(event) => updateFilter("mode", event.target.value)}>
              <option value="">All modes</option>
              <option value={DeliveryMode.IN_PERSON}>In person</option>
              <option value={DeliveryMode.ONLINE}>Online</option>
            </select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="managed-appointment-from">From</Label>
            <Input id="managed-appointment-from" type="date" value={fromDate} onChange={(event) => updateFilter("from", event.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="managed-appointment-to">To</Label>
            <Input id="managed-appointment-to" type="date" value={toDate} onChange={(event) => updateFilter("to", event.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="managed-appointment-order">Order</Label>
            <select id="managed-appointment-order" className={controlClass} value={ordering} onChange={(event) => updateFilter("ordering", event.target.value)}>
              <option value={AppointmentListOrdering.START_ASC}>Soonest first</option>
              <option value={AppointmentListOrdering.START_DESC}>Latest first</option>
            </select>
          </div>
          <Button type="submit" variant="secondary">Search</Button>
        </form>
      </div>

      {list.isPending ? (
        <div aria-busy="true" className="space-y-3 py-5">
          <Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" />
          <p className="sr-only">Loading Appointments…</p>
        </div>
      ) : list.isError ? (
        <div role="alert" className="border-y border-danger/30 py-6">
          <p className="text-sm text-danger">
            {appointmentErrorMessage(list.error, "Appointments within your scope could not be loaded.")}
          </p>
          <Button className="mt-4" variant="secondary" onClick={() => void list.refetch()}>Retry</Button>
        </div>
      ) : items.length === 0 ? (
        <div className="border-y border-border py-8">
          <p className="text-sm text-muted">
            {hasFilters
              ? "No Appointments match the selected filters within your scope."
              : status === AppointmentStatus.SCHEDULED
                ? "No scheduled Appointments are available within your operational scope."
                : "No Appointments are available within your operational scope."}
          </p>
          {hasFilters || status !== undefined ? (
            <Link
              href={updateAppointmentQuery(
                pathname,
                new URLSearchParams(searchParams.toString()),
                { search: "", status: "ALL", mode: "", from: "", to: "" },
              )}
              className="mt-3 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              {hasFilters ? "Clear filters" : "Show all statuses"}
            </Link>
          ) : null}
          {page > 1 || pageData?.has_next ? (
            <PaginationControls
              page={pageData?.page ?? page}
              hasNext={pageData?.has_next ?? false}
              onPrevious={() => movePage(page - 1)}
              onNext={() => movePage(page + 1)}
            />
          ) : null}
        </div>
      ) : (
        <>
          {list.isFetching ? <p role="status" className="mt-4 text-xs text-muted">Refreshing Appointments…</p> : null}
          <div className="mt-4 hidden overflow-x-auto md:block">
            <table className="w-full min-w-[1000px] border-collapse text-left text-sm">
              <caption className="sr-only">Appointments within your authorized operational scope</caption>
              <thead className="border-y border-border bg-surface-muted text-xs text-muted">
                <tr>
                  <th scope="col" className="px-3 py-3 font-semibold">Appointment</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Student</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Service</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Counselor</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Date and time</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Delivery</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((appointment) => (
                  <tr key={appointment.id}>
                    <th scope="row" className="px-3 py-4 font-normal">
                      <Link href={`/portal/appointments/${appointment.id}`} className="font-mono text-xs font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{appointment.reference_code}</Link>
                    </th>
                    <td className="px-3 py-4">
                      <p className="font-medium text-ink">{appointment.student.display_name}</p>
                      {appointment.student.institutional_id ? <p className="mt-1 break-all text-xs text-muted">{appointment.student.institutional_id}</p> : null}
                    </td>
                    <td className="px-3 py-4 text-ink">{appointment.service.name}</td>
                    <td className="px-3 py-4 text-ink">{appointment.provider.display_name}</td>
                    <td className="px-3 py-4 text-ink">{formatAppointmentDateTime(appointment.starts_at, appointment.ends_at)}</td>
                    <td className="px-3 py-4 text-ink">{deliveryModeLabel(appointment.delivery_mode)}</td>
                    <td className="px-3 py-4"><AppointmentStatusBadge status={appointment.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="mt-4 divide-y divide-border border-y border-border md:hidden">
            {items.map((appointment) => (
              <li key={appointment.id} className="py-4">
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
          <PaginationControls
            page={pageData?.page ?? page}
            hasNext={pageData?.has_next ?? false}
            onPrevious={() => movePage(page - 1)}
            onNext={() => movePage(page + 1)}
          />
        </>
      )}
    </section>
  );
}

export function AppointmentsManagedPage() {
  const { user } = usePortalSession();
  if (!user.capabilities.includes("appointments.manage")) {
    return (
      <AppointmentsUnavailable>
        Your current access does not include operational Appointment management.
      </AppointmentsUnavailable>
    );
  }
  return <ManagedAppointmentsList />;
}
