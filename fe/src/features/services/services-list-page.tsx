"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  replaceServicesQueryParam,
  ServicesListSkeleton,
  ServicesPageHeading,
  ServicesQueryError,
  ServicesSearchField,
  ServicesStatusBadge,
  ServicesSystemRequiredBadge,
  servicesSelectClass,
} from "@/features/services/services-shared";
import { isSystemRequiredService } from "@/features/services/system-required-service";
import {
  AppointmentPolicy,
  DeliveryMode,
} from "@/lib/api/generated/model";
import { useServicesList } from "@/lib/api/generated/services/services";

function isAppointmentPolicy(value: string | null): value is AppointmentPolicy {
  return (
    value !== null &&
    Object.values(AppointmentPolicy).includes(value as AppointmentPolicy)
  );
}

function policyLabel(policy: AppointmentPolicy): string {
  if (policy === AppointmentPolicy.NONE) return "No appointment";
  if (policy === AppointmentPolicy.OPTIONAL) return "Appointment optional";
  return "Appointment required";
}

function descriptionExcerpt(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "No description provided.";
  return trimmed.length > 180 ? trimmed.slice(0, 177) + "…" : trimmed;
}

export function ServicesListPage() {
  const { user } = usePortalSession();
  const canManage = user.capabilities.includes("services.manage");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const search = (searchParams.get("search") ?? "").slice(0, 160).trim();
  const requestedPolicy = searchParams.get("appointment_policy");
  const appointmentPolicy = isAppointmentPolicy(requestedPolicy)
    ? requestedPolicy
    : undefined;
  const requestedPage = Number.parseInt(searchParams.get("page") ?? "1", 10);
  const page = Number.isFinite(requestedPage) && requestedPage > 0
    ? requestedPage
    : 1;
  const includeInactive =
    canManage && searchParams.get("include_inactive") === "true";

  const list = useServicesList(
    {
      ...(includeInactive ? { include_inactive: true } : {}),
      ...(search ? { search } : {}),
      ...(appointmentPolicy
        ? { appointment_policy: appointmentPolicy }
        : {}),
      page,
      page_size: 20,
    },
    { query: { retry: false } },
  );

  function updatePolicy(value: string) {
    router.replace(
      replaceServicesQueryParam(
        pathname,
        new URLSearchParams(searchParams.toString()),
        "appointment_policy",
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

  const hasFilters = Boolean(search || appointmentPolicy);

  return (
    <section aria-labelledby="services-heading">
      <div id="services-heading" className="sr-only">
        Services
      </div>
      <ServicesPageHeading
        title="Services"
        action={
          canManage ? (
            <Link
              href="/portal/services/new"
              className="inline-flex min-h-10 items-center justify-center rounded-md border border-brand bg-brand px-4 py-2 text-sm font-semibold text-on-brand transition-colors hover:bg-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body"
            >
              Create Service
            </Link>
          ) : null
        }
      />

      <div className="mt-8 border-y border-border py-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
          <ServicesSearchField />
          <div className="lg:w-64">
            <Label htmlFor="services-policy-filter">Appointment policy</Label>
            <select
              id="services-policy-filter"
              className={servicesSelectClass + " mt-2"}
              value={appointmentPolicy ?? ""}
              onChange={(event) => updatePolicy(event.target.value)}
            >
              <option value="">All appointment policies</option>
              <option value={AppointmentPolicy.NONE}>No appointment</option>
              <option value={AppointmentPolicy.OPTIONAL}>
                Appointment optional
              </option>
              <option value={AppointmentPolicy.REQUIRED}>
                Appointment required
              </option>
            </select>
          </div>
        </div>
        {canManage ? (
          <label className="mt-4 inline-flex min-h-10 items-center gap-3 text-sm font-medium text-ink">
            <input
              type="checkbox"
              className="h-4 w-4 accent-brand"
              checked={includeInactive}
              onChange={(event) => updateInactive(event.target.checked)}
            />
            Include inactive Services
          </label>
        ) : null}
      </div>

      {list.isPending ? (
        <ServicesListSkeleton />
      ) : list.isError ? (
        <div className="mt-6">
          <ServicesQueryError
            error={list.error}
            fallback="Services could not be loaded."
            onRetry={() => void list.refetch()}
          />
        </div>
      ) : list.data.data.items.length === 0 ? (
        <p className="border-b border-border py-10 text-sm text-muted">
          {hasFilters
            ? "No Services match the current search or filters."
            : canManage && includeInactive
              ? "No Services are configured yet."
              : "No active Services are currently available."}
        </p>
      ) : (
        <>
          {list.isFetching ? (
            <p role="status" className="mt-4 text-xs text-muted">
              Refreshing Services…
            </p>
          ) : null}
          <ul className="mt-5 divide-y divide-border border-y border-border">
            {list.data.data.items.map((service) => (
              <li
                key={service.id}
                className="grid gap-4 py-5 md:grid-cols-[minmax(0,1fr)_15rem] md:items-start"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={"/portal/services/" + service.id}
                      className="font-heading text-lg font-semibold text-ink hover:text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    >
                      {service.name}
                    </Link>
                    {canManage ? (
                      <ServicesStatusBadge active={service.is_active} />
                    ) : null}
                    {isSystemRequiredService(service) ? (
                      <ServicesSystemRequiredBadge />
                    ) : null}
                  </div>
                  <p className="mt-1 font-mono text-xs text-muted">
                    {service.code}
                  </p>
                  <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
                    {descriptionExcerpt(service.description)}
                  </p>
                </div>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm md:grid-cols-1">
                  <div>
                    <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                      Delivery
                    </dt>
                    <dd className="mt-1 text-ink">
                      {service.delivery_modes.length === 0
                        ? "Not configured"
                        : [
                            service.delivery_modes.includes(
                              DeliveryMode.IN_PERSON,
                            )
                              ? "In person"
                              : null,
                            service.delivery_modes.includes(DeliveryMode.ONLINE)
                              ? "Online"
                              : null,
                          ]
                            .filter(Boolean)
                            .join(", ")}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                      Appointment
                    </dt>
                    <dd className="mt-1 text-ink">
                      {policyLabel(service.appointment_policy)}
                      {service.appointment_policy !== AppointmentPolicy.NONE &&
                      service.default_duration_minutes !== null
                        ? " · " +
                          service.default_duration_minutes +
                          " min"
                        : ""}
                    </dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
          {page > 1 || list.data.data.has_next ? (
            <nav
              aria-label="Services pagination"
              className="mt-5 flex items-center justify-between gap-4"
            >
              <Button
                variant="secondary"
                disabled={page <= 1}
                onClick={() => movePage(page - 1)}
              >
                Previous
              </Button>
              <span className="text-sm text-muted">
                Page {list.data.data.page}
              </span>
              <Button
                variant="secondary"
                disabled={!list.data.data.has_next}
                onClick={() => movePage(page + 1)}
              >
                Next
              </Button>
            </nav>
          ) : null}
        </>
      )}
    </section>
  );
}
