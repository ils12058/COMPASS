"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AppointmentStatusBadge,
  AppointmentsLocalNavigation,
  AppointmentsPageHeading,
  AppointmentsUnavailable,
  PaginationControls,
  appointmentErrorMessage,
  deliveryModeLabel,
  formatAppointmentDateTime,
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
  const status = isStatus(statusParam)
    ? statusParam
    : statusParam === "ALL"
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

  return (
    <section aria-labelledby="my-appointments-heading">
      <AppointmentsLocalNavigation />
      <AppointmentsPageHeading
        headingId="my-appointments-heading"
        title="My appointments"
        description={
          access.isStudent
            ? "View your scheduled and past Appointments."
            : "View Appointments assigned to you as Counselor."
        }
      />

      <div className="mb-6 grid gap-4 border-y border-border py-5 sm:grid-cols-2 xl:grid-cols-4">
        <div className="grid gap-2">
          <Label htmlFor="my-appointment-status">Status</Label>
          <select
            id="my-appointment-status"
            className="min-h-10 rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            value={status ?? "ALL"}
            onChange={(event) => updateFilter("status", event.target.value)}
          >
            <option value={AppointmentStatus.SCHEDULED}>Scheduled</option>
            <option value="ALL">All statuses</option>
            <option value={AppointmentStatus.CANCELLED}>Cancelled</option>
            <option value={AppointmentStatus.COMPLETED}>Completed</option>
            <option value={AppointmentStatus.NO_SHOW}>No-show</option>
          </select>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="my-appointment-from">From date</Label>
          <input
            id="my-appointment-from"
            type="date"
            className="min-h-10 rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            value={fromDate}
            onChange={(event) => updateFilter("from", event.target.value)}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="my-appointment-to">To date</Label>
          <input
            id="my-appointment-to"
            type="date"
            className="min-h-10 rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            value={toDate}
            onChange={(event) => updateFilter("to", event.target.value)}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="my-appointment-order">Order</Label>
          <select
            id="my-appointment-order"
            className="min-h-10 rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            value={ordering}
            onChange={(event) => updateFilter("ordering", event.target.value)}
          >
            <option value={AppointmentListOrdering.START_ASC}>Soonest first</option>
            <option value={AppointmentListOrdering.START_DESC}>Latest first</option>
          </select>
        </div>
      </div>

      {list.isPending ? (
        <div aria-busy="true" className="space-y-3 py-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <p className="sr-only">Loading Appointments…</p>
        </div>
      ) : list.isError ? (
        <div role="alert" className="border-y border-danger/30 py-6">
          <p className="text-sm text-danger">
            {appointmentErrorMessage(list.error, "My Appointments could not be loaded.")}
          </p>
          <Button className="mt-4" variant="secondary" onClick={() => void list.refetch()}>
            Retry
          </Button>
        </div>
      ) : items.length === 0 ? (
        <div className="border-y border-border py-8">
          <p className="text-sm text-muted">
            {filtering
              ? "No Appointments match the selected filters."
              : status === AppointmentStatus.SCHEDULED
                ? "No scheduled Appointments match this view."
                : "No Appointments are available."}
          </p>
          {status !== undefined || fromDate || toDate ? (
            <Link
              href={updateAppointmentQuery(
                pathname,
                new URLSearchParams(searchParams.toString()),
                { status: "ALL", from: "", to: "" },
              )}
              className="mt-3 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              {filtering ? "Clear filters" : "Show all statuses"}
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
          {list.isFetching ? (
            <p role="status" className="mb-3 text-xs text-muted">Refreshing Appointments…</p>
          ) : null}

          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[760px] border-collapse text-left text-sm">
              <caption className="sr-only">My Appointments</caption>
              <thead className="border-y border-border bg-surface-muted text-xs text-muted">
                <tr>
                  <th scope="col" className="px-3 py-3 font-semibold">{access.isStudent ? "Service" : "Student"}</th>
                  <th scope="col" className="px-3 py-3 font-semibold">{access.isStudent ? "Counselor" : "Service"}</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Date and time</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Delivery</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((appointment) => (
                  <tr key={appointment.id}>
                    <th scope="row" className="px-3 py-4 font-normal">
                      <Link href={`/portal/appointments/${appointment.id}`} className="font-semibold text-ink hover:text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                        {access.isStudent ? appointment.service.name : appointment.student.display_name}
                      </Link>
                      <p className="mt-1 font-mono text-xs text-muted">{appointment.reference_code}</p>
                      {!access.isStudent && appointment.student.institutional_id ? (
                        <p className="mt-1 break-all text-xs text-muted">{appointment.student.institutional_id}</p>
                      ) : null}
                    </th>
                    <td className="px-3 py-4 text-ink">
                      {access.isStudent ? appointment.provider.display_name : appointment.service.name}
                    </td>
                    <td className="px-3 py-4 text-ink">{formatAppointmentDateTime(appointment.starts_at, appointment.ends_at)}</td>
                    <td className="px-3 py-4 text-ink">{deliveryModeLabel(appointment.delivery_mode)}</td>
                    <td className="px-3 py-4"><AppointmentStatusBadge status={appointment.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="divide-y divide-border border-y border-border md:hidden">
            {items.map((appointment) => (
              <li key={appointment.id} className="py-4">
                <article>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link href={`/portal/appointments/${appointment.id}`} className="break-words font-semibold text-ink hover:text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
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

export function AppointmentsMyPage() {
  const { user } = usePortalSession();
  const access = getAppointmentAccess(user);
  if (!access.canViewSelf) return <AppointmentsUnavailable />;
  return <MyAppointmentsList access={access} />;
}
