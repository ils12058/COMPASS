"use client";

import { FormEvent, useState } from "react";
import { Clock3, LoaderCircle, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useAvailabilityGetProviderEffective,
} from "@/lib/api/generated/availability/availability";
import type {
  AvailabilityGetProviderEffectiveDeliveryMode,
  AvailabilityGetProviderEffectiveParams,
  ServiceResponse,
} from "@/lib/api/generated/model";
import { AvailabilityGetProviderEffectiveDeliveryMode as DeliveryModeValues } from "@/lib/api/generated/model";
import { useServicesList } from "@/lib/api/generated/services/services";
import {
  AvailabilityActionMessage,
  AvailabilityEmptyState,
  AvailabilityListSkeleton,
  AvailabilityManagementRequired,
  AvailabilityQueryError,
  AvailabilitySection,
  availabilitySelectClassName,
  formatAvailabilityDateTime,
  formatAvailabilityValue,
  toDateInputValue,
} from "@/features/portal/admin/availability/portal-it-admin-availability-shared";

function addDays(date: Date, days: number) {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

function serviceModes(service: ServiceResponse | undefined) {
  return service?.delivery_modes.filter(
    (mode): mode is AvailabilityGetProviderEffectiveDeliveryMode =>
      mode === DeliveryModeValues.IN_PERSON || mode === DeliveryModeValues.ONLINE,
  ) ?? [];
}

export function PortalItAdminEffectiveAvailability({
  canManage,
  providerId,
  providerName,
}: {
  canManage: boolean;
  providerId: string;
  providerName: string;
}) {
  const [serviceId, setServiceId] = useState("");
  const [deliveryMode, setDeliveryMode] = useState<
    AvailabilityGetProviderEffectiveDeliveryMode | ""
  >("");
  const [startDate, setStartDate] = useState(() => toDateInputValue(new Date()));
  const [endDate, setEndDate] = useState(() => toDateInputValue(addDays(new Date(), 6)));
  const [appliedParams, setAppliedParams] = useState<
    AvailabilityGetProviderEffectiveParams | null
  >(null);
  const [error, setError] = useState<string | null>(null);
  const servicesQuery = useServicesList(
    { include_inactive: false, page: 1, page_size: 50 },
    {
      query: {
        enabled: canManage && Boolean(providerId),
        retry: false,
        staleTime: 30_000,
      },
    },
  );
  const services = servicesQuery.data?.data.items ?? [];
  const selectedService = services.find((service) => service.id === serviceId) ?? services[0];
  const selectedModes = serviceModes(selectedService);
  const effectiveServiceId = selectedService?.id ?? "";
  const effectiveDeliveryMode = selectedModes.includes(
    deliveryMode as AvailabilityGetProviderEffectiveDeliveryMode,
  )
    ? deliveryMode
    : selectedModes[0] ?? "";
  const effectiveParams =
    appliedParams ??
    ({
      delivery_mode: DeliveryModeValues.IN_PERSON,
      end_date: endDate,
      service_id: effectiveServiceId,
      start_date: startDate,
    } satisfies AvailabilityGetProviderEffectiveParams);
  const effectiveQuery = useAvailabilityGetProviderEffective(providerId, effectiveParams, {
    query: {
      enabled: canManage && Boolean(providerId && appliedParams),
      retry: false,
      staleTime: 15_000,
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!effectiveServiceId || !effectiveDeliveryMode) {
      setError("Choose a service and delivery mode first.");
      return;
    }

    if (!startDate || !endDate || startDate > endDate) {
      setError("Choose an end date on or after the start date.");
      return;
    }

    setAppliedParams({
      delivery_mode: effectiveDeliveryMode,
      end_date: endDate,
      service_id: effectiveServiceId,
      start_date: startDate,
    });
  }

  return (
    <AvailabilitySection
      icon={Clock3}
      title="Effective availability"
      description={`Preview the hours when ${providerName || "a provider"} and the office overlap for a selected service.`}
    >
      {!canManage ? (
        <AvailabilityManagementRequired />
      ) : !providerId ? (
        <p className="text-sm leading-6 text-muted-foreground">
          Choose a provider above to preview their effective availability.
        </p>
      ) : servicesQuery.isPending ? (
        <AvailabilityListSkeleton label="Loading services for availability" />
      ) : servicesQuery.isError ? (
        <AvailabilityQueryError
          message="We couldn’t load the services needed for this preview."
          onRetry={() => void servicesQuery.refetch()}
        />
      ) : (
        <div className="space-y-6">
          <form
            className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 sm:p-5"
            onSubmit={submit}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="effective-service">Service</Label>
                <select
                  id="effective-service"
                  className={`${availabilitySelectClassName} mt-2`}
                  value={effectiveServiceId}
                  onChange={(event) => {
                    setServiceId(event.target.value);
                    setAppliedParams(null);
                  }}
                >
                  <option value="">Choose a service</option>
                  {services.map((service) => (
                    <option key={service.id} value={service.id}>
                      {service.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="effective-delivery-mode">Delivery mode</Label>
                <select
                  id="effective-delivery-mode"
                  className={`${availabilitySelectClassName} mt-2`}
                  disabled={!selectedModes.length}
                  value={effectiveDeliveryMode}
                  onChange={(event) => {
                    setDeliveryMode(
                      event.target.value as AvailabilityGetProviderEffectiveDeliveryMode,
                    );
                    setAppliedParams(null);
                  }}
                >
                  <option value="">Choose a mode</option>
                  {selectedModes.map((mode) => (
                    <option key={mode} value={mode}>
                      {formatAvailabilityValue(mode)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="effective-start-date">Start date</Label>
                <Input
                  id="effective-start-date"
                  className="mt-2 h-10"
                  required
                  type="date"
                  value={startDate}
                  onChange={(event) => {
                    setStartDate(event.target.value);
                    setAppliedParams(null);
                  }}
                />
              </div>
              <div>
                <Label htmlFor="effective-end-date">End date</Label>
                <Input
                  id="effective-end-date"
                  className="mt-2 h-10"
                  min={startDate}
                  required
                  type="date"
                  value={endDate}
                  onChange={(event) => {
                    setEndDate(event.target.value);
                    setAppliedParams(null);
                  }}
                />
              </div>
            </div>
            <AvailabilityActionMessage error={error} />
            <div className="mt-4 flex justify-end">
              <Button disabled={effectiveQuery.isFetching} type="submit">
                {effectiveQuery.isFetching ? (
                  <LoaderCircle aria-hidden="true" className="animate-spin" />
                ) : (
                  <Search aria-hidden="true" />
                )}
                {effectiveQuery.isFetching ? "Checking…" : "Check availability"}
              </Button>
            </div>
          </form>

          {appliedParams && effectiveQuery.isPending ? (
            <AvailabilityListSkeleton label="Checking effective availability" />
          ) : appliedParams && effectiveQuery.isError ? (
            <AvailabilityQueryError onRetry={() => void effectiveQuery.refetch()} />
          ) : effectiveQuery.data?.data ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <span className="rounded-full bg-[var(--compass-support-soft)] px-2.5 py-1 font-semibold text-[var(--compass-support-strong)]">
                  {formatAvailabilityValue(effectiveQuery.data.data.delivery_mode)}
                </span>
                <span>{effectiveQuery.data.data.timezone}</span>
                <span>
                  {effectiveQuery.data.data.start_date} – {effectiveQuery.data.data.end_date}
                </span>
              </div>
              {effectiveQuery.data.data.windows.length ? (
                <div className="space-y-3">
                  {effectiveQuery.data.data.windows.map((window, index) => (
                    <div
                      key={`${window.starts_at}-${window.ends_at}-${index}`}
                      className="rounded-2xl border border-[var(--compass-border)] p-4"
                    >
                      <p className="font-semibold">
                        {formatAvailabilityDateTime(window.starts_at)} – {formatAvailabilityDateTime(window.ends_at)}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <AvailabilityEmptyState
                  description="There is no overlapping office and provider availability in this date range."
                  title="No overlapping hours"
                />
              )}
            </div>
          ) : (
            <AvailabilityEmptyState
              description="Choose the service, delivery mode, and date range to preview available hours."
              title="Ready when you are"
            />
          )}
        </div>
      )}
    </AvailabilitySection>
  );
}
