"use client";

import { Plus } from "lucide-react";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { PageActionLink } from "@/components/ui/page-action";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { SortField } from "@/components/ui/sort-field";
import { useListOrdering } from "@/features/portal/components/list-ordering";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import {
  replaceServicesQueryParam,
  serviceBookingLabel,
  serviceDeliveryLabel,
  serviceOrderingOptions,
  ServicesListSkeleton,
  ServicesPageHeading,
  servicesErrorMessage,
  ServicesStatusBadge,
  ServicesSystemRequiredBadge,
} from "@/features/services/services-shared";
import { ServiceOrdering } from "@/lib/api/generated/model";
import { useServicesList } from "@/lib/api/generated/services/services";

type BookingFilter = "available" | "not_available";

function bookingFilter(value: string | null): BookingFilter | undefined {
  return value === "available" || value === "not_available" ? value : undefined;
}

function descriptionExcerpt(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "";
  return trimmed.length > 180 ? trimmed.slice(0, 177) + "…" : trimmed;
}

export function ServicesListPage() {
  const { user } = usePortalSession();
  const canManage = user.capabilities.includes("services.manage");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const search = (searchParams.get("search") ?? "").slice(0, 160).trim();
  // URL search owns the applied query. A self-issued acknowledgement must leave newer
  // typing alone; an external search change adopts the URL. Popstate explicitly restores
  // history, even when its term also occurred among our pending navigations.
  const [searchDraft, setSearchDraft] = useState({
    applied: search,
    value: search,
    issued: [] as string[],
  });
  if (searchDraft.applied !== search) {
    const acknowledgement = searchDraft.issued.indexOf(search);
    setSearchDraft({
      applied: search,
      value: acknowledgement >= 0 ? searchDraft.value : search,
      issued: acknowledgement >= 0 ? searchDraft.issued.slice(acknowledgement + 1) : [],
    });
  }
  const searchValue = searchDraft.value;
  const searchTimer = useRef<number | null>(null);

  function cancelPendingSearch() {
    if (searchTimer.current !== null) window.clearTimeout(searchTimer.current);
    searchTimer.current = null;
  }

  useEffect(() => {
    const restore = () => {
      if (searchTimer.current !== null) window.clearTimeout(searchTimer.current);
      searchTimer.current = null;
      const value = (new URLSearchParams(window.location.search).get("search") ?? "").slice(0, 160).trim();
      setSearchDraft({ applied: value, value, issued: [] });
    };
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);

  useEffect(() => {
    const trimmed = searchValue.trim();
    if (trimmed === search) return;
    searchTimer.current = window.setTimeout(() => {
      searchTimer.current = null;
      const next = new URLSearchParams(searchParams.toString());
      if (trimmed) next.set("search", trimmed);
      else next.delete("search");
      next.delete("page");
      setSearchDraft((draft) => ({ ...draft, issued: [...draft.issued, trimmed] }));
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    }, 350);
    return () => {
      if (searchTimer.current !== null) window.clearTimeout(searchTimer.current);
      searchTimer.current = null;
    };
  }, [pathname, router, search, searchParams, searchValue]);

  const booking = bookingFilter(searchParams.get("appointment_booking"));
  const requestedPage = Number.parseInt(searchParams.get("page") ?? "1", 10);
  const page = Number.isFinite(requestedPage) && requestedPage > 0
    ? requestedPage
    : 1;
  const includeInactive =
    canManage && searchParams.get("include_inactive") === "true";
  const { requested: requestedOrdering, setOrdering } = useListOrdering(ServiceOrdering);

  const list = useServicesList(
    {
      ...(includeInactive ? { include_inactive: true } : {}),
      ...(search ? { search } : {}),
      ...(booking ? { appointment_booking_enabled: booking === "available" } : {}),
      ...(requestedOrdering ? { ordering: requestedOrdering } : {}),
      page,
      page_size: 20,
    },
    { query: { retry: false } },
  );

  function updateBooking(value: string) {
    router.replace(
      replaceServicesQueryParam(
        pathname,
        new URLSearchParams(searchParams.toString()),
        "appointment_booking",
        value,
      ),
      { scroll: false },
    );
  }

  function updateInactive(checked: boolean) {
    router.replace(
      replaceServicesQueryParam(
        pathname,
        new URLSearchParams(searchParams.toString()),
        "include_inactive",
        checked ? "true" : "",
      ),
      { scroll: false },
    );
  }

  function movePage(nextPage: number) {
    router.push(
      replaceServicesQueryParam(
        pathname,
        new URLSearchParams(searchParams.toString()),
        "page",
        String(nextPage),
        false,
      ),
    );
  }

  function clearFilters() {
    cancelPendingSearch();
    setSearchDraft((draft) => ({ ...draft, value: "", issued: [...draft.issued, ""] }));
    router.replace(requestedOrdering ? `${pathname}?ordering=${requestedOrdering}` : pathname, { scroll: false });
  }

  const hasFilters = Boolean(search || booking);

  return (
    <section aria-labelledby="services-heading">
      <div id="services-heading" className="sr-only">
        Services
      </div>
      <ServicesPageHeading
        title="Services"
        action={
          canManage ? (
            <PageActionLink href="/portal/services/new" icon={Plus} label="Create" labelDetail="Service" />
          ) : null
        }
      />

      {/* The search applies as you type and the other choices apply on change. */}
      <FloatingListTools
        label="Service search and filters"
        filterCount={[booking, includeInactive].filter(Boolean).length}
        clear={hasFilters || includeInactive ? (
          <Button
            variant="quiet"
            // Clearing the filters keeps the chosen order; sorting is not a filter.
            onClick={clearFilters}
          >
            Clear filters
          </Button>
        ) : undefined}
        filters={<>
          <FilterField label="Appointment booking" htmlFor="services-booking-filter" className="sm:col-span-2">
            <Select
              id="services-booking-filter"
              value={booking ?? ""}
              onChange={(event) => updateBooking(event.target.value)}
            >
              <option value="">All</option>
              <option value="available">Available</option>
              <option value="not_available">Not available</option>
            </Select>
          </FilterField>
        {canManage ? (
          <label className="inline-flex min-h-10 items-center gap-3 text-sm font-medium text-ink sm:col-span-2">
            <input
              type="checkbox"
              className="h-4 w-4 accent-brand"
              checked={includeInactive}
              onChange={(event) => updateInactive(event.target.checked)}
            />
            Include inactive Services
          </label>
        ) : null}
        </>}
      >
        <ListSearchField id="services-search" label="Search Services" maxLength={160}
          placeholder="Search by Service name or code" value={searchValue}
          onChange={(event) => setSearchDraft((draft) => ({ ...draft, value: event.target.value }))} />
      </FloatingListTools>

      <Panel aria-labelledby="services-results-heading">
        <PanelHeader
          title="Service Catalog"
          titleId="services-results-heading"
          actions={
            <SortField
              id="services-sort"
              value={requestedOrdering ?? list.data?.data.ordering}
              options={serviceOrderingOptions}
              onChange={setOrdering}
            />
          }
          context={list.isFetching && !list.isPending
            ? "Refreshing Services…"
            : list.isSuccess
              ? describeResultPage({ count: list.data.data.items.length, page: list.data.data.page, hasNext: list.data.data.has_next, noun: { one: "Service", other: "Services" }, filtered: hasFilters })
              : null}
        />
      {list.isPending ? (
        <ServicesListSkeleton framed={false} />
      ) : list.isError ? (
        <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void list.refetch()}>Retry</Button>}>
          {servicesErrorMessage(list.error, "Services could not be loaded.")}
        </PanelMessage>
      ) : list.data.data.items.length === 0 ? (
        <PanelMessage>
          {hasFilters
            ? "No services match the current search or filters."
            : canManage && includeInactive
              ? "No Services are configured yet."
              : "No active Services are currently available."}
        </PanelMessage>
      ) : (
          <ul className="divide-y divide-border">
            {list.data.data.items.map((service) => (
              <li
                key={service.id}
                className="grid grid-cols-[minmax(0,1fr)] gap-4 px-4 py-4 sm:px-5 md:grid-cols-[minmax(0,1fr)_15rem] md:items-start"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={"/portal/services/" + service.id}
                      className="min-w-0 [overflow-wrap:anywhere] font-heading text-lg font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    >
                      {service.name}
                    </Link>
                    {canManage ? (
                      <ServicesStatusBadge active={service.is_active} />
                    ) : null}
                    {service.is_system_required ? (
                      <ServicesSystemRequiredBadge />
                    ) : null}
                  </div>
                  <p className="mt-1 [overflow-wrap:anywhere] font-mono text-xs text-muted">
                    {service.code}
                  </p>
                  {service.description.trim() ? (
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
                      {descriptionExcerpt(service.description)}
                    </p>
                  ) : null}
                </div>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm md:grid-cols-1">
                  <div>
                    <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                      Delivery
                    </dt>
                    <dd className="mt-1 text-ink">
                      {serviceDeliveryLabel(service.delivery_modes)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                      Appointment booking
                    </dt>
                    <dd className="mt-1 text-ink">
                      {serviceBookingLabel(service.appointment_booking_enabled)}
                      {service.appointment_booking_enabled &&
                      service.default_appointment_duration_minutes !== null
                        ? " · " + service.default_appointment_duration_minutes + " min"
                        : ""}
                    </dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
      )}
      {!list.isPending && !list.isError ? (
        <CanonicalPagination
          className="border-brand-line px-4 py-3 sm:px-5"
          page={list.data.data.page}
          hasNext={list.data.data.has_next}
          label="Services pagination"
          onPageChange={movePage}
        />
      ) : null}
      </Panel>
    </section>
  );
}
