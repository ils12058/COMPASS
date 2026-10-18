"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useInfiniteQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { AppointmentListOrdering } from "@/lib/api/generated/model";
import type {
  AppointmentResponse,
  AppointmentStatus,
  AppointmentsListManagedParams,
  AppointmentsListMyParams,
  DeliveryMode,
} from "@/lib/api/generated/model";
import {
  appointmentsListManaged,
  appointmentsListMy,
  getAppointmentsListManagedQueryKey,
  getAppointmentsListMyQueryKey,
} from "@/lib/api/generated/appointments/appointments";
import { INSTITUTION_TIME_ZONE } from "@/lib/institutional-time";
import {
  appointmentErrorMessage,
  appointmentStatusLabel,
} from "@/features/appointments/appointments-shared";

const CALENDAR_PAGE_SIZE = 50;
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export type AppointmentPresentation = "list" | "calendar";
export type AppointmentCalendarView = "month" | "week";
export type AppointmentCalendarSource = "my" | "managed";

export type AppointmentCalendarFilters = {
  search?: string;
  status?: AppointmentStatus;
  upcoming?: boolean;
  fromDate?: string;
  toDate?: string;
  serviceId?: string;
  deliveryMode?: DeliveryMode;
};

export function AppointmentsPresentationToggle({
  value,
  onChange,
}: {
  value: AppointmentPresentation;
  onChange: (next: AppointmentPresentation) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Appointment presentation"
      className="inline-flex flex-wrap gap-1 rounded-sm border border-brand-line bg-surface-raised p-1"
    >
      <Button
        variant={value === "list" ? "secondary" : "quiet"}
        aria-pressed={value === "list"}
        onClick={() => onChange("list")}
      >
        List
      </Button>
      <Button
        variant={value === "calendar" ? "secondary" : "quiet"}
        aria-pressed={value === "calendar"}
        onClick={() => onChange("calendar")}
      >
        Calendar
      </Button>
    </div>
  );
}

function dateKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function addDays(date: Date, count: number): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + count);
}

function startOfWeek(date: Date): Date {
  return addDays(date, -date.getDay());
}

function monthBounds(date: Date) {
  return {
    start: new Date(date.getFullYear(), date.getMonth(), 1),
    end: new Date(date.getFullYear(), date.getMonth() + 1, 0),
  };
}

function weekBounds(date: Date) {
  const start = startOfWeek(date);
  return { start, end: addDays(start, 6) };
}

function daysBetween(start: Date, end: Date): Date[] {
  const days: Date[] = [];
  for (let day = start; dateKey(day) <= dateKey(end); day = addDays(day, 1)) {
    days.push(day);
  }
  return days;
}

function moveMonth(date: Date, direction: number): Date {
  const targetMonth = new Date(date.getFullYear(), date.getMonth() + direction, 1);
  const lastDay = new Date(targetMonth.getFullYear(), targetMonth.getMonth() + 1, 0).getDate();
  return new Date(targetMonth.getFullYear(), targetMonth.getMonth(), Math.min(date.getDate(), lastDay));
}

function dateInTimeZone(value: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const values = new Map(parts.filter((part) => part.type !== "literal").map((part) => [part.type, part.value]));
  return `${values.get("year")}-${values.get("month")}-${values.get("day")}`;
}

function rangeQueryDates(
  start: Date,
  end: Date,
  filters: AppointmentCalendarFilters,
): { fromDate: string; toDate: string; isEmpty: boolean } {
  const startInstant = new Date(start.getFullYear(), start.getMonth(), start.getDate());
  const endExclusive = new Date(end.getFullYear(), end.getMonth(), end.getDate() + 1);
  const rangeFrom = dateInTimeZone(startInstant, INSTITUTION_TIME_ZONE);
  const rangeTo = dateInTimeZone(new Date(endExclusive.getTime() - 1), INSTITUTION_TIME_ZONE);
  const fromDate = filters.fromDate && filters.fromDate > rangeFrom ? filters.fromDate : rangeFrom;
  const toDate = filters.toDate && filters.toDate < rangeTo ? filters.toDate : rangeTo;
  return { fromDate, toDate, isEmpty: fromDate > toDate };
}

function useAppointmentsCalendarQuery({
  active,
  source,
  filters,
  fromDate,
  toDate,
  emptyRange,
}: {
  active: boolean;
  source: AppointmentCalendarSource;
  filters: AppointmentCalendarFilters;
  fromDate: string;
  toDate: string;
  emptyRange: boolean;
}) {
  const commonParams: AppointmentsListMyParams = {
    ...(filters.search ? { search: filters.search } : {}),
    ...(filters.status ? { status: filters.status } : {}),
    ...(filters.upcoming ? { upcoming: true } : {}),
    from_date: fromDate,
    to_date: toDate,
    ordering: AppointmentListOrdering.EARLIEST_START,
    page_size: CALENDAR_PAGE_SIZE,
  };
  const managedParams: AppointmentsListManagedParams = {
    ...commonParams,
    ...(filters.serviceId ? { service_id: filters.serviceId } : {}),
    ...(filters.deliveryMode ? { delivery_mode: filters.deliveryMode } : {}),
  };
  const queryKey = source === "my"
    ? [...getAppointmentsListMyQueryKey(commonParams), "calendar"] as const
    : [...getAppointmentsListManagedQueryKey(managedParams), "calendar"] as const;

  const appointments = useInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam, signal }) => source === "my"
      ? appointmentsListMy({ ...commonParams, page: pageParam }, { signal })
      : appointmentsListManaged({ ...managedParams, page: pageParam }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (last) => last.data.has_next ? last.data.page + 1 : undefined,
    enabled: active && !emptyRange,
    retry: false,
  });
  const hasNextPage = appointments.hasNextPage;
  const isError = appointments.isError;
  const isFetching = appointments.isFetching;
  const fetchNextPage = appointments.fetchNextPage;

  // A calendar range must never silently stop at the first server page.
  useEffect(() => {
    if (!active || emptyRange || isError || !hasNextPage || isFetching) return;
    void fetchNextPage();
  }, [active, emptyRange, fetchNextPage, hasNextPage, isError, isFetching]);

  return appointments;
}

const statusClasses: Record<AppointmentStatus, string> = {
  SCHEDULED: "border-info/30 bg-info/10 text-info",
  CANCELLED: "border-border-strong bg-surface-muted text-muted",
  COMPLETED: "border-success/30 bg-success/10 text-success",
  NO_SHOW: "border-warning/30 bg-warning/10 text-warning",
};

function localTime(date: Date): string {
  return new Intl.DateTimeFormat("en-PH", { hour: "numeric", minute: "2-digit" }).format(date);
}

function localDateLabel(date: Date, options?: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat("en-PH", options ?? {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function formatTimeRange(appointment: AppointmentResponse): string {
  const start = new Date(appointment.starts_at);
  const end = new Date(appointment.ends_at);
  const endLabel = dateKey(start) === dateKey(end)
    ? localTime(end)
    : `${localDateLabel(end, { month: "short", day: "numeric" })} ${localTime(end)}`;
  return `${localTime(start)}–${endLabel}`;
}

function appointmentTone(status: AppointmentStatus): string {
  return statusClasses[status] ?? "border-border bg-surface-muted text-muted";
}

function CalendarEvent({
  appointment,
  isStudent,
}: {
  appointment: AppointmentResponse;
  isStudent: boolean;
}) {
  const start = new Date(appointment.starts_at);
  const title = isStudent ? appointment.service.name : appointment.student.display_name;
  const service = isStudent ? null : appointment.service.name;
  const startLabel = localDateLabel(start);
  const timeLabel = formatTimeRange(appointment);
  const statusLabel = appointmentStatusLabel(appointment.status);
  const accessibleName = `${startLabel}, ${timeLabel}, ${title}${service ? `, ${service}` : ""}, ${statusLabel}. Open appointment details.`;

  return (
    <Link
      href={`/portal/appointments/${appointment.id}`}
      aria-label={accessibleName}
      className={`block min-w-0 rounded-sm border px-2 py-1.5 text-sm leading-5 transition-colors hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${appointmentTone(appointment.status)}`}
    >
      <span className="block font-semibold">{localTime(start)}</span>
      <span className="block truncate font-medium" title={title}>{title}</span>
      {service ? <span className="block truncate text-muted" title={service}>{service}</span> : null}
      <span className="block text-xs font-semibold">{statusLabel}</span>
    </Link>
  );
}

function MonthCalendar({
  anchor,
  days,
  eventsByDay,
  today,
  isStudent,
  onShowWeek,
}: {
  anchor: Date;
  days: Date[];
  eventsByDay: Map<string, AppointmentResponse[]>;
  today: string;
  isStudent: boolean;
  onShowWeek: (date: Date) => void;
}) {
  const firstWeekday = days[0]?.getDay() ?? 0;
  const cells: (Date | null)[] = [
    ...Array.from({ length: firstWeekday }, () => null),
    ...days,
  ];
  while (cells.length % 7 !== 0) cells.push(null);
  const monthName = localDateLabel(anchor, { month: "long", year: "numeric" });

  return (
    <div className="hidden min-w-0 md:block" role="region" aria-label={`${monthName} appointment calendar`}>
      <ol aria-label="Days of the week" className="grid grid-cols-7 border-b border-brand-line bg-brand-wash">
        {WEEKDAYS.map((weekday) => (
          <li key={weekday} aria-label={weekday} className="px-2 py-2 text-center text-xs font-semibold text-brand sm:px-3 sm:text-sm">
            <span className="hidden sm:inline">{weekday}</span>
            <span className="sm:hidden" aria-hidden="true">{weekday.slice(0, 1)}</span>
          </li>
        ))}
      </ol>
      <ol className="grid grid-cols-7">
        {cells.map((day, index) => day === null ? (
          <li key={`blank-${index}`} aria-hidden="true" className="min-h-28 border-b border-r border-border-subtle bg-surface-muted/40 last:border-r-0" />
        ) : (
          <li
            key={dateKey(day)}
            aria-label={localDateLabel(day)}
            className="min-h-28 min-w-0 border-b border-r border-border-subtle p-1.5 last:border-r-0 sm:p-2"
          >
            <time
              dateTime={dateKey(day)}
              aria-current={dateKey(day) === today ? "date" : undefined}
              className={`inline-flex min-h-7 min-w-7 items-center justify-center rounded-full px-1 text-sm ${dateKey(day) === today ? "bg-brand text-on-brand" : "font-medium text-ink"}`}
            >
              {day.getDate()}
            </time>
            <ul className="mt-1 space-y-1">
              {(eventsByDay.get(dateKey(day)) ?? []).slice(0, 3).map((appointment) => (
                <li key={appointment.id} className="min-w-0">
                  <CalendarEvent appointment={appointment} isStudent={isStudent} />
                </li>
              ))}
              {(eventsByDay.get(dateKey(day))?.length ?? 0) > 3 ? (
                <li>
                  <Button
                    variant="quiet"
                    className="min-h-8 w-full justify-start px-1.5 text-xs"
                    aria-label={`Show ${(eventsByDay.get(dateKey(day))?.length ?? 0) - 3} more appointments for ${localDateLabel(day)}`}
                    onClick={() => onShowWeek(day)}
                  >
                    +{(eventsByDay.get(dateKey(day))?.length ?? 0) - 3} more
                  </Button>
                </li>
              ) : null}
            </ul>
          </li>
        ))}
      </ol>
    </div>
  );
}

function AgendaCalendar({
  days,
  eventsByDay,
  today,
  isStudent,
  label,
}: {
  days: Date[];
  eventsByDay: Map<string, AppointmentResponse[]>;
  today: string;
  isStudent: boolean;
  label: string;
}) {
  return (
    <ol className="divide-y divide-border md:hidden" aria-label={`${label} appointment agenda`}>
      {days.map((day) => {
        const key = dateKey(day);
        const events = eventsByDay.get(key) ?? [];
        return (
          <li key={key} className="px-4 py-3 sm:px-5">
            <h3 className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm font-semibold text-ink">
              <time dateTime={key} aria-current={key === today ? "date" : undefined}>{localDateLabel(day)}</time>
              {key === today ? <span className="rounded-full bg-brand-wash px-2 py-0.5 text-xs text-brand">Today</span> : null}
            </h3>
            {events.length ? (
              <ul className="mt-2 space-y-2">
                {events.map((appointment) => (
                  <li key={appointment.id}>
                    <CalendarEvent appointment={appointment} isStudent={isStudent} />
                  </li>
                ))}
              </ul>
            ) : <p className="mt-1 text-sm text-muted">No appointments</p>}
          </li>
        );
      })}
    </ol>
  );
}

export function AppointmentsCalendar({
  active,
  source,
  filters,
  isStudent,
  initialDate,
}: {
  active: boolean;
  source: AppointmentCalendarSource;
  filters: AppointmentCalendarFilters;
  isStudent: boolean;
  initialDate: Date | null;
}) {
  const [anchorOverride, setAnchorOverride] = useState<Date | null>(null);
  const [todayOverride, setTodayOverride] = useState<Date | null>(null);
  const [view, setView] = useState<AppointmentCalendarView>("month");
  const anchor = anchorOverride ?? initialDate;

  const bounds = anchor
    ? view === "month" ? monthBounds(anchor) : weekBounds(anchor)
    : null;
  const periodDays = bounds ? daysBetween(bounds.start, bounds.end) : [];
  const localStart = bounds ? dateKey(bounds.start) : "1970-01-01";
  const localEnd = bounds ? dateKey(bounds.end) : "1970-01-01";
  const queryDates = bounds ? rangeQueryDates(bounds.start, bounds.end, filters) : null;
  const query = useAppointmentsCalendarQuery({
    active: active && anchor !== null,
    source,
    filters,
    fromDate: queryDates?.fromDate ?? "1970-01-01",
    toDate: queryDates?.toDate ?? "1970-01-01",
    emptyRange: queryDates?.isEmpty ?? true,
  });

  const appointments = (query.data?.pages.flatMap((page) => page.data.items) ?? [])
    .filter((appointment) => {
      const date = new Date(appointment.starts_at);
      return !Number.isNaN(date.getTime()) && dateKey(date) >= localStart && dateKey(date) <= localEnd;
    })
    .sort((left, right) => left.starts_at.localeCompare(right.starts_at));
  const eventsByDay = new Map<string, AppointmentResponse[]>();
  for (const appointment of appointments) {
    const key = dateKey(new Date(appointment.starts_at));
    eventsByDay.set(key, [...(eventsByDay.get(key) ?? []), appointment]);
  }
  const today = dateKey(todayOverride ?? initialDate ?? new Date(0));
  const periodLabel = anchor
    ? view === "month"
      ? localDateLabel(anchor, { month: "long", year: "numeric" })
      : `${localDateLabel(periodDays[0], { month: "short", day: "numeric" })}–${localDateLabel(periodDays.at(-1)!, { month: "short", day: "numeric", year: "numeric" })}`
    : "Loading calendar";
  const empty = queryDates?.isEmpty || (query.data !== undefined && appointments.length === 0);
  const loadingAllPages = query.isPending || query.hasNextPage || query.isFetchingNextPage;

  function movePeriod(direction: number) {
    if (!anchor) return;
    setAnchorOverride(view === "month" ? moveMonth(anchor, direction) : addDays(anchor, direction * 7));
  }

  return (
    <Panel hidden={!active} aria-labelledby="appointment-calendar-heading">
      <PanelHeader
        title="Calendar"
        titleId="appointment-calendar-heading"
        context={anchor ? (query.isFetchingNextPage ? "Loading more appointments…" : null) : null}
      />
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-brand-line px-4 py-3 sm:px-5">
        <div role="group" aria-label="Calendar navigation" className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" aria-label={`Previous ${view}`} onClick={() => movePeriod(-1)}>Previous</Button>
          <Button
            variant="secondary"
            onClick={() => {
              const now = new Date();
              setAnchorOverride(now);
              setTodayOverride(now);
            }}
          >Today</Button>
          <Button variant="secondary" aria-label={`Next ${view}`} onClick={() => movePeriod(1)}>Next</Button>
        </div>
        <h3 aria-live="polite" aria-atomic="true" className="order-first w-full font-heading text-base font-semibold text-ink sm:order-none sm:w-auto">
          {periodLabel}
        </h3>
        <div role="group" aria-label="Calendar period" className="inline-flex gap-1">
          {(["month", "week"] as const).map((option) => (
            <Button
              key={option}
              variant={view === option ? "secondary" : "quiet"}
              aria-pressed={view === option}
              onClick={() => setView(option)}
            >
              {option === "month" ? "Month" : "Week"}
            </Button>
          ))}
        </div>
      </div>

      {query.isError ? (
        <PanelMessage
          role="alert"
          tone="danger"
          action={<Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button>}
        >
          {appointmentErrorMessage(query.error, "Appointments for this period could not be loaded.")}
        </PanelMessage>
      ) : queryDates?.isEmpty ? (
        <PanelMessage>No appointments in this period.</PanelMessage>
      ) : !anchor || loadingAllPages ? (
        <PanelMessage role="status">Loading appointments for this period…</PanelMessage>
      ) : empty ? (
        <PanelMessage>No appointments in this period.</PanelMessage>
      ) : null}

      {anchor && !query.isError && !loadingAllPages && !queryDates?.isEmpty ? (
        view === "month" ? (
          <>
            <MonthCalendar
              anchor={anchor}
              days={periodDays}
              eventsByDay={eventsByDay}
              today={today}
              isStudent={isStudent}
              onShowWeek={(date) => {
                setAnchorOverride(date);
                setView("week");
              }}
            />
            <AgendaCalendar
              days={periodDays}
              eventsByDay={eventsByDay}
              today={today}
              isStudent={isStudent}
              label={periodLabel}
            />
          </>
        ) : (
          <>
            <div className="hidden md:block">
              <WeekCalendar days={periodDays} eventsByDay={eventsByDay} today={today} isStudent={isStudent} />
            </div>
            <AgendaCalendar
              days={periodDays}
              eventsByDay={eventsByDay}
              today={today}
              isStudent={isStudent}
              label={periodLabel}
            />
          </>
        )
      ) : null}
    </Panel>
  );
}

function WeekCalendar({
  days,
  eventsByDay,
  today,
  isStudent,
}: {
  days: Date[];
  eventsByDay: Map<string, AppointmentResponse[]>;
  today: string;
  isStudent: boolean;
}) {
  return (
    <ol className="grid grid-cols-7" aria-label="Appointment week">
      {days.map((day) => {
        const key = dateKey(day);
        const events = eventsByDay.get(key) ?? [];
        return (
          <li key={key} aria-label={localDateLabel(day)} className="min-w-0 border-r border-border-subtle p-2 last:border-r-0">
            <h4 className={`mb-2 rounded-sm px-1 py-2 text-center text-sm font-semibold ${key === today ? "bg-brand-wash text-brand" : "text-ink"}`}>
              <span className="block text-xs font-medium text-muted">{WEEKDAYS[day.getDay()].slice(0, 3)}</span>
              <time dateTime={key} aria-current={key === today ? "date" : undefined}>{day.getDate()}</time>
              {key === today ? <span className="sr-only">, Today</span> : null}
            </h4>
            <ul className="space-y-2">
              {events.map((appointment) => (
                <li key={appointment.id}>
                  <CalendarEvent appointment={appointment} isStudent={isStudent} />
                </li>
              ))}
              {events.length === 0 ? <li className="py-1 text-center text-xs text-muted">No appointments</li> : null}
            </ul>
          </li>
        );
      })}
    </ol>
  );
}
