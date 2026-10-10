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
import { DeliveryMode, type ServiceResponse } from "@/lib/api/generated/model";
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

// The page size used for Service matches. Past it, the reader is asked to refine the search rather
// than page through Services inside the preview's form.
const SERVICE_MATCH_LIMIT = 50;

export function EffectiveAvailabilityPreview({
  providerId,
  refreshToken,
}: {
  providerId: string;
  refreshToken: number;
}) {
  const initialToday = useMemo(() => institutionalDateInputValue(), []);
  const [serviceSearch, setServiceSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [selectedService, setSelectedService] = useState<ServiceResponse | null>(null);
  const [mode, setMode] = useState<DeliveryMode | "">("");
  const [startDate, setStartDate] = useState(initialToday);
  const [throughDate, setThroughDate] = useState(() =>
    addCalendarDays(initialToday, 6),
  );
  const [request, setRequest] = useState<PreviewRequest | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const previousRefreshToken = useRef(refreshToken);

  // The search applies shortly after typing stops, like the Counselor directory's search.
  useEffect(() => {
    const next = serviceSearch.trim();
    if (next === appliedSearch) return;
    const timer = window.setTimeout(() => setAppliedSearch(next), 300);
    return () => window.clearTimeout(timer);
  }, [appliedSearch, serviceSearch]);

  // Active Services only (the list's default), matched by the Services API's own search.
  const services = useServicesList(
    { ...(appliedSearch ? { search: appliedSearch } : {}), page: 1, page_size: SERVICE_MATCH_LIMIT },
    { query: { retry: false } },
  );
  const serviceData = safeQueryData(services)?.data;
  const matches = serviceData?.items ?? [];
  // The chosen Service stays chosen while the search changes, even when it no longer matches.
  const options =
    selectedService && !matches.some((service) => service.id === selectedService.id)
      ? [selectedService, ...matches]
      : matches;

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

  function chooseService(nextId: string) {
    setSelectedService(options.find((service) => service.id === nextId) ?? null);
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

  const noServicesAtAll = serviceData !== undefined && !appliedSearch && matches.length === 0 && !selectedService;

  return (
    <Panel aria-labelledby="effective-availability-heading">
      <PanelHeader
        title="Schedule preview"
        titleId="effective-availability-heading"
        description="Where office hours, counselor hours, time off, and service rules overlap. Appointments already booked are not reflected here."
      />
      <div className="px-4 py-4 *:first:mt-0 sm:px-5">

      {services.isError && serviceData ? <RefreshFailureNotice onRetry={() => void services.refetch()} retrying={services.isFetching} /> : null}
      {services.isPending && !appliedSearch && !selectedService ? (
        <AvailabilitySectionSkeleton label="Loading services…" />
      ) : !serviceData && !services.isPending ? (
        <div className="mt-5">
          <AvailabilityQueryError
            error={services.error}
            fallback="Active Services could not be loaded."
            onRetry={() => void services.refetch()}
          />
        </div>
      ) : noServicesAtAll ? (
        <p className="mt-4 text-sm text-muted">
          No active Services are currently available for this preview.
        </p>
      ) : (
        <form
          className="mt-4 rounded-sm bg-surface-subtle p-4"
          onSubmit={submit}
        >
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className="grid content-start gap-2 md:col-span-2">
              <Label htmlFor="effective-service-search">Find a Service</Label>
              <Input
                id="effective-service-search"
                type="search"
                value={serviceSearch}
                placeholder="Search by Service name or code"
                aria-describedby="effective-service-matches"
                onChange={(event) => setServiceSearch(event.target.value)}
              />
              <Label htmlFor="effective-service" className="mt-1">Service</Label>
              <Select
                id="effective-service"
                value={selectedService?.id ?? ""}
                onChange={(event) => chooseService(event.target.value)}
              >
                <option value="">{matches.length === 0 && appliedSearch ? "No matching Services" : "Select a Service"}</option>
                {options.map((service) => (
                  <option key={service.id} value={service.id}>
                    {service.name}
                  </option>
                ))}
              </Select>
              <p id="effective-service-matches" aria-live="polite" className="text-xs leading-5 text-muted">
                {services.isFetching && appliedSearch
                  ? "Searching Services…"
                  : appliedSearch && matches.length === 0
                    ? "No active Services match this search."
                    : serviceData?.has_next
                      ? `Showing the first ${matches.length} matches. Refine the search to find others.`
                      : null}
              </p>
            </div>
            <div className="grid content-start gap-2">
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
            <div className="grid content-start gap-2">
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
              <Label htmlFor="effective-through" className="mt-1">Through</Label>
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

          {localError ? (
            <p role="alert" className="mt-4 text-sm text-danger">
              {localError}
            </p>
          ) : null}

          <div className="mt-4">
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
          <div className="mt-5">
            <p className="text-xs text-muted">
              Timezone: {effectiveData.timezone === INSTITUTION_TIME_ZONE ? INSTITUTION_TIME_ZONE_LABEL : effectiveData.timezone}
            </p>
            <dl className="mt-2 divide-y divide-border">
              {grouped.map((group) => (
                <div key={group.key} className="grid gap-x-6 gap-y-1 py-2.5 sm:grid-cols-[minmax(11rem,auto)_1fr]">
                  <dt className="text-sm font-semibold text-ink">{group.label}</dt>
                  <dd className="text-sm text-muted">
                    {group.windows
                      .map((window) => timeLabel(window.starts_at, effectiveData.timezone) + " – " + timeLabel(window.ends_at, effectiveData.timezone))
                      .join(" · ")}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )}
        </>
      ) : null}
      </div>
    </Panel>
  );
}
