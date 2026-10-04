"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Panel, PanelHeader } from "@/components/ui/panel";
import {
  AvailabilityQueryError,
  AvailabilitySectionSkeleton,
} from "@/features/availability/availability-shared";
import { DeliveryMode } from "@/lib/api/generated/model";
import { useAvailabilityGetProviderEffective } from "@/lib/api/generated/availability/availability";
import { useServicesList } from "@/lib/api/generated/services/services";
import { INSTITUTION_TIME_ZONE, INSTITUTION_TIME_ZONE_LABEL, institutionalDateInputValue } from "@/lib/institutional-time";

type PreviewRequest = {
  service_id: string;
  delivery_mode: DeliveryMode;
  start_date: string;
  end_date: string;
};

function addCalendarDays(value: string, days: number): string {
  const parts = value.split("-").map(Number);
  if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part))) {
    return value;
  }
  const date = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2] + days));
  return (
    String(date.getUTCFullYear()) +
    "-" +
    String(date.getUTCMonth() + 1).padStart(2, "0") +
    "-" +
    String(date.getUTCDate()).padStart(2, "0")
  );
}

function dateDistanceDays(start: string, endExclusive: string): number {
  const startParts = start.split("-").map(Number);
  const endParts = endExclusive.split("-").map(Number);
  if (
    startParts.length !== 3 ||
    endParts.length !== 3 ||
    startParts.some((part) => !Number.isFinite(part)) ||
    endParts.some((part) => !Number.isFinite(part))
  ) {
    return Number.NaN;
  }

  const startValue = Date.UTC(
    startParts[0],
    startParts[1] - 1,
    startParts[2],
  );
  const endValue = Date.UTC(endParts[0], endParts[1] - 1, endParts[2]);
  return (endValue - startValue) / 86_400_000;
}

function deliveryModeLabel(mode: DeliveryMode): string {
  return mode === DeliveryMode.ONLINE ? "Online" : "In person";
}

function zonedDateKey(value: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(value));
  const year = parts.find((part) => part.type === "year")?.value ?? "";
  const month = parts.find((part) => part.type === "month")?.value ?? "";
  const day = parts.find((part) => part.type === "day")?.value ?? "";
  return year + "-" + month + "-" + day;
}

function dateLabel(value: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-PH", {
    timeZone,
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(new Date(value));
}

function timeLabel(value: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-PH", {
    timeZone,
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function EffectiveAvailabilityPreview({
  providerId,
  refreshToken,
}: {
  providerId: string;
  refreshToken: number;
}) {
  const initialToday = useMemo(() => institutionalDateInputValue(), []);
  const [servicePage, setServicePage] = useState(1);
  const [serviceId, setServiceId] = useState("");
  const [mode, setMode] = useState<DeliveryMode | "">("");
  const [startDate, setStartDate] = useState(initialToday);
  const [throughDate, setThroughDate] = useState(() =>
    addCalendarDays(initialToday, 6),
  );
  const [request, setRequest] = useState<PreviewRequest | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const previousRefreshToken = useRef(refreshToken);

  const services = useServicesList(
    { page: servicePage, page_size: 50 },
    { query: { retry: false } },
  );
  const serviceData = safeQueryData(services)?.data;
  const selectedService = serviceData?.items.find(
    (service) => service.id === serviceId,
  );

  const effective = useAvailabilityGetProviderEffective(
    providerId,
    request ?? {
      service_id: "",
      delivery_mode: DeliveryMode.IN_PERSON,
      start_date: "1970-01-01",
      end_date: "1970-01-02",
    },
    { query: { enabled: request !== null, retry: false } },
  );
  const effectiveData = safeQueryData(effective)?.data;

  useEffect(() => {
    if (previousRefreshToken.current === refreshToken) return;
    previousRefreshToken.current = refreshToken;
    if (request) void effective.refetch();
  }, [effective, refreshToken, request]);

  function changeServicePage(next: number) {
    setServicePage(next);
    setServiceId("");
    setMode("");
    setRequest(null);
    setLocalError(null);
  }

  function chooseService(nextId: string) {
    setServiceId(nextId);
    setMode("");
    setRequest(null);
    setLocalError(null);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);

    if (!selectedService) {
      setLocalError("Select an active Service.");
      return;
    }
    if (!mode) {
      setLocalError("Select a delivery mode supported by the Service.");
      return;
    }

    const endExclusive = addCalendarDays(throughDate, 1);
    const days = dateDistanceDays(startDate, endExclusive);
    if (!Number.isFinite(days) || days <= 0) {
      setLocalError("The Through date must be on or after the Start date.");
      return;
    }
    if (days > 31) {
      setLocalError("Effective Availability may cover at most 31 days.");
      return;
    }

    setRequest({
      service_id: selectedService.id,
      delivery_mode: mode,
      start_date: startDate,
      end_date: endExclusive,
    });
  }

  const grouped = useMemo(() => {
    const response = effectiveData;
    if (!response) return [];
    const groups = new Map<
      string,
      { label: string; windows: { starts_at: string; ends_at: string }[] }
    >();

    for (const window of response.windows) {
      const key = zonedDateKey(window.starts_at, response.timezone);
      const existing = groups.get(key);
      if (existing) {
        existing.windows.push(window);
      } else {
        groups.set(key, {
          label: dateLabel(window.starts_at, response.timezone),
          windows: [window],
        });
      }
    }

    return Array.from(groups.entries()).map(([key, value]) => ({
      key,
      ...value,
    }));
  }, [effectiveData]);

  return (
    <Panel aria-labelledby="effective-availability-heading">
      <PanelHeader
        title="Schedule preview"
        titleId="effective-availability-heading"
        description="Where office hours, counselor hours, time off, and service rules overlap. Appointments already booked are not reflected here."
      />
      <div className="px-4 py-4 *:first:mt-0 sm:px-5">

      {services.isError && serviceData ? <RefreshFailureNotice onRetry={() => void services.refetch()} retrying={services.isFetching} /> : null}
      {services.isPending ? (
        <AvailabilitySectionSkeleton label="Loading Services…" />
      ) : !serviceData ? (
        <div className="mt-5">
          <AvailabilityQueryError
            error={services.error}
            fallback="Active Services could not be loaded."
            onRetry={() => void services.refetch()}
          />
        </div>
      ) : serviceData.items.length === 0 ? (
        <p className="mt-4 text-sm text-muted">
          No active Services are currently available for this preview.
        </p>
      ) : (
        <form
          className="mt-4 rounded-sm bg-surface-subtle p-4"
          onSubmit={submit}
        >
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className="grid gap-2 md:col-span-2">
              <Label htmlFor="effective-service">Service</Label>
              <Select
                id="effective-service"
                value={serviceId}
                onChange={(event) => chooseService(event.target.value)}
              >
                <option value="">Select a Service</option>
                {serviceData.items.map((service) => (
                  <option key={service.id} value={service.id}>
                    {service.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="effective-mode">Delivery mode</Label>
              <Select
                id="effective-mode"
                value={mode}
                disabled={!selectedService}
                onChange={(event) => {
                  setMode(event.target.value as DeliveryMode | "");
                  setRequest(null);
                  setLocalError(null);
                }}
              >
                <option value="">Select a mode</option>
                {selectedService?.delivery_modes.map((deliveryMode) => (
                  <option key={deliveryMode} value={deliveryMode}>
                    {deliveryModeLabel(deliveryMode)}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="effective-start">Start date</Label>
              <Input
                id="effective-start"
                type="date"
                required
                value={startDate}
                onChange={(event) => {
                  setStartDate(event.target.value);
                  setRequest(null);
                }}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="effective-through">Through</Label>
              <Input
                id="effective-through"
                type="date"
                required
                value={throughDate}
                onChange={(event) => {
                  setThroughDate(event.target.value);
                  setRequest(null);
                }}
              />
            </div>
          </div>

          {servicePage > 1 || serviceData.has_next ? (
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Button
                variant="secondary"
                disabled={servicePage <= 1}
                onClick={() => changeServicePage(servicePage - 1)}
              >
                Previous Services
              </Button>
              <span className="text-sm text-muted">
                Service page {serviceData.page}
              </span>
              <Button
                variant="secondary"
                disabled={!serviceData.has_next}
                onClick={() => changeServicePage(servicePage + 1)}
              >
                Next Services
              </Button>
            </div>
          ) : null}

          {localError ? (
            <p role="alert" className="mt-4 text-sm text-danger">
              {localError}
            </p>
          ) : null}

          <div className="mt-5">
            <Button type="submit">Preview effective availability</Button>
          </div>
        </form>
      )}

      {request ? (
        <>
        {effective.isError && effectiveData ? <RefreshFailureNotice onRetry={() => void effective.refetch()} retrying={effective.isFetching} /> : null}
        {effective.isPending ? (
          <AvailabilitySectionSkeleton label="Loading effective Availability…" />
        ) : !effectiveData ? (
          <div className="mt-5">
            <AvailabilityQueryError
              error={effective.error}
              fallback="Effective Availability could not be loaded."
              onRetry={() => void effective.refetch()}
            />
          </div>
        ) : effectiveData.windows.length === 0 ? (
          <p className="mt-5 text-sm text-muted">
            No effective Availability exists for this Service, delivery mode,
            and date range.
          </p>
        ) : (
          <div className="mt-6">
            <p className="text-xs text-muted">
              Timezone: {effectiveData.timezone === INSTITUTION_TIME_ZONE ? INSTITUTION_TIME_ZONE_LABEL : effectiveData.timezone}
            </p>
            <div className="mt-3 divide-y divide-border rounded-sm border border-border">
              {grouped.map((group) => (
                <section key={group.key} className="px-4 py-4">
                  <h3 className="font-semibold text-ink">{group.label}</h3>
                  <ul className="mt-2 space-y-1 text-sm text-muted">
                    {group.windows.map((window) => (
                      <li key={window.starts_at + window.ends_at}>
                        {timeLabel(
                          window.starts_at,
                          effectiveData.timezone,
                        )}{" "}
                        –{" "}
                        {timeLabel(
                          window.ends_at,
                          effectiveData.timezone,
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          </div>
        )}
        </>
      ) : null}
      </div>
    </Panel>
  );
}
