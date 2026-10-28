"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import {
  AppointmentStatusBadge,
  deliveryModeLabel,
  formatAppointmentTime,
} from "@/features/appointments/appointments-shared";
import { OverviewAnnouncements } from "@/features/portal/home/overview-announcements";
import type { OverviewAttentionData } from "@/features/portal/home/overview-work";
import {
  getCounselorHomeDestinations,
  getHeadGuidanceHomeDestinations,
  type CounselorHomeDestination,
} from "@/features/portal/home/counselor-home-presentation";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { useProjectionFocus } from "@/features/freshness/use-projection-focus";
import { AppointmentListOrdering, AppointmentStatus, type AppointmentResponse, type UserSummary } from "@/lib/api/generated/model";
import {
  getAppointmentsListMyQueryKey,
  useAppointmentsListMy,
} from "@/lib/api/generated/appointments/appointments";
import { INSTITUTION_TIME_ZONE_LABEL, institutionalDateInputValue } from "@/lib/institutional-time";

const AGENDA_PAGE_SIZE = 5;
const appointmentsMyQueryFamily = getAppointmentsListMyQueryKey();

export function getCounselorAgendaParams(today: string) {
  return {
    status: AppointmentStatus.SCHEDULED,
    from_date: today,
    to_date: today,
    ordering: AppointmentListOrdering.EARLIEST_START,
    page: 1,
    page_size: AGENDA_PAGE_SIZE,
  };
}

function destinationList(destinations: CounselorHomeDestination[]) {
  return (
    <ul className="grid @min-[32rem]:grid-cols-2">
      {destinations.map((destination) => (
        <li key={destination.href} className="border-b border-border">
          <Link
            href={destination.href}
            className="group flex min-h-11 items-center justify-between gap-3 py-3 pr-4 text-sm transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus"
          >
            <span className="min-w-0 [overflow-wrap:anywhere]">
              <span className="block font-semibold text-brand group-hover:underline">{destination.label}</span>
            </span>
            <ArrowRight aria-hidden="true" className="h-4 w-4 shrink-0" />
          </Link>
        </li>
      ))}
    </ul>
  );
}

function CounselorAgenda({ user, today }: { user: UserSummary; today: string }) {
  const access = getAppointmentAccess(user);
  const appointments = useAppointmentsListMy(getCounselorAgendaParams(today), {
    query: {
      enabled: access.canViewSelf,
      retry: false,
      refetchInterval: 60_000,
      refetchIntervalInBackground: false,
      refetchOnWindowFocus: "always",
      refetchOnReconnect: "always",
    },
  });
  useProjectionFocus(appointmentsMyQueryFamily, access.canViewSelf);

  if (!access.canViewSelf) return null;

  const page = safeQueryData(appointments)?.data;
  const items = page?.items ?? [];
  const todayHref = `/portal/appointments/my?status=${AppointmentStatus.SCHEDULED}&from=${today}&to=${today}`;

  return (
    <Panel className="border-0 bg-transparent" aria-labelledby="counselor-agenda-heading">
      <PanelHeader
        className="border-border px-0 sm:px-0"
        title={<span className="[overflow-wrap:anywhere]">{"Today's appointments"}</span>}
        titleId="counselor-agenda-heading"
        description={INSTITUTION_TIME_ZONE_LABEL}
        actions={(
          <Link
            href={todayHref}
            className="inline-flex min-h-11 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            View today’s schedule <span aria-hidden="true" className="ml-1">→</span>
          </Link>
        )}
      />

      {appointments.isError && page ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
          <p role="status" className="text-sm text-muted">
            Today’s schedule could not be refreshed. Showing the last confirmed appointments.
          </p>
          <Button variant="secondary" onClick={() => void appointments.refetch()}>Retry</Button>
        </div>
      ) : null}

      {appointments.isPending ? (
        <LoadingRegion label="Loading today's appointments…" className="space-y-4 px-4 py-4 sm:px-5">
          {[0, 1, 2].map((row) => (
            <div key={row} aria-hidden="true" className="space-y-2 border-b border-border pb-4 last:border-0 last:pb-0">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          ))}
        </LoadingRegion>
      ) : appointments.isError && !page ? (
        <PanelMessage
          role="alert"
          tone="danger"
          action={(
            <Button variant="secondary" onClick={() => void appointments.refetch()}>
              Retry
            </Button>
          )}
        >
          Today’s appointments could not be loaded.
        </PanelMessage>
      ) : items.length === 0 ? (
        <PanelMessage>No scheduled appointments today.</PanelMessage>
      ) : (
        <>
          <ul className="divide-y divide-border">
            {items.map((appointment) => <CounselorAgendaRow key={appointment.id} appointment={appointment} />)}
          </ul>
          {page?.has_next ? (
            <PanelMessage className="border-t border-border" role="status">
              Showing the first {AGENDA_PAGE_SIZE} appointments. More are scheduled today.
            </PanelMessage>
          ) : null}
        </>
      )}
    </Panel>
  );
}

function CounselorAgendaRow({ appointment }: { appointment: AppointmentResponse }) {
  return (
    <li className="min-w-0 py-3.5">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <p className="font-semibold tabular-nums text-ink">
          <time dateTime={appointment.starts_at}>{formatAppointmentTime(appointment.starts_at)}</time>
          <span aria-hidden="true">–</span>
          <time dateTime={appointment.ends_at}>{formatAppointmentTime(appointment.ends_at)}</time>
          <span className="sr-only"> {INSTITUTION_TIME_ZONE_LABEL}</span>
        </p>
        <AppointmentStatusBadge status={appointment.status} />
      </div>
      <h3 className="mt-1 min-w-0 [overflow-wrap:anywhere] text-base font-semibold leading-6">
        <Link
          href={`/portal/appointments/${appointment.id}`}
          aria-label={`Open appointment with ${appointment.student.display_name}`}
          className="flex min-h-11 w-full min-w-0 items-center text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus [overflow-wrap:anywhere]"
        >
          {appointment.student.display_name}
        </Link>
      </h3>
      <p className="mt-0.5 min-w-0 [overflow-wrap:anywhere] text-sm leading-6 text-muted">
        {appointment.service.name} <span aria-hidden="true">·</span> {deliveryModeLabel(appointment.delivery_mode)}
      </p>
    </li>
  );
}

function CounselorMyWork({ data }: { data: OverviewAttentionData }) {
  const initialError = data.items.some((item) => item.id === "work-unavailable");

  return (
    <Panel aria-labelledby="counselor-work-heading">
      <PanelHeader
        title="My work"
        titleId="counselor-work-heading"
        actions={data.viewAllWork && !initialError ? (
          <Link
            href="/portal/work"
            className="inline-flex min-h-11 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            View all work <span aria-hidden="true" className="ml-1">→</span>
          </Link>
        ) : undefined}
      />

      {data.staleNotices.map((notice) => (
        <div key={notice} className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
          <p role="status" className="text-sm text-muted">{notice}</p>
          {data.retryWork ? <Button variant="secondary" onClick={data.retryWork}>Retry</Button> : null}
        </div>
      ))}

      {data.items.length > 0 ? (
        <ul className="divide-y divide-border">
          {data.items.map((item) => (
            <li
              key={item.id}
              role={item.isError ? "alert" : undefined}
              className="grid min-w-0 gap-2 px-4 py-3.5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-4 sm:px-5"
            >
              <div className="min-w-0 [overflow-wrap:anywhere]">
                <h3 className="font-semibold leading-6 text-ink">{item.title}</h3>
                {item.subject ? <p className="mt-0.5 text-sm text-ink">{item.subject}</p> : null}
                {item.priorityLabel ? <p className="mt-0.5 text-xs font-semibold text-muted">{item.priorityLabel}</p> : null}
                <p className="mt-0.5 text-sm leading-6 text-muted">{item.detail}</p>
              </div>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 sm:justify-end">
                <Link
                  href={item.href}
                  className="inline-flex min-h-11 items-center rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                >
                  {item.actionLabel} <span aria-hidden="true" className="ml-1">→</span>
                </Link>
                {item.onRetry ? (
                  <Button variant="secondary" onClick={item.onRetry}>Retry</Button>
                ) : null}
              </div>
            </li>
          ))}
          {data.isPending ? (
            <li aria-hidden="true" className="space-y-2 px-4 py-4 sm:px-5">
              <Skeleton className="h-4 w-44" />
              <Skeleton className="h-4 w-2/3" />
            </li>
          ) : null}
        </ul>
      ) : data.isPending ? (
        <LoadingRegion label="Checking My work…" className="space-y-3 px-4 py-4 sm:px-5">
          <Skeleton aria-hidden="true" className="h-4 w-44" />
          <Skeleton aria-hidden="true" className="h-4 w-2/3" />
          <Skeleton aria-hidden="true" className="h-4 w-1/2" />
        </LoadingRegion>
      ) : data.isCaughtUp ? (
        <PanelMessage>No items currently need attention in My work.</PanelMessage>
      ) : null}

      {data.workHasNext ? (
        <PanelMessage className="border-t border-border" role="status">
          Showing the first 5 items. More work is available in the full queue.
        </PanelMessage>
      ) : null}
    </Panel>
  );
}

function CounselorDestinations({ user }: { user: UserSummary }) {
  const destinations = getCounselorHomeDestinations(user);
  if (destinations.length === 0) return null;
  return (
    <Panel className="@container border-0 bg-transparent" aria-labelledby="counselor-continuation-heading">
      <PanelHeader className="border-border px-0 sm:px-0" title="Continue in your workspace" titleId="counselor-continuation-heading" />
      {destinationList(destinations)}
    </Panel>
  );
}

function HeadGuidanceDestinations({ user }: { user: UserSummary }) {
  const destinations = getHeadGuidanceHomeDestinations(user);
  if (destinations.length === 0) return null;
  return (
    <Panel className="@container border-0 bg-transparent" aria-labelledby="head-guidance-oversight-heading">
      <PanelHeader className="border-border px-0 sm:px-0" title="Authorized oversight" titleId="head-guidance-oversight-heading" />
      {destinationList(destinations)}
    </Panel>
  );
}

export function CounselorHome({
  user,
  attention,
  summary,
  now,
}: {
  user: UserSummary;
  attention: OverviewAttentionData;
  summary: ReactNode;
  now: Date;
}) {
  const today = institutionalDateInputValue(now);
  const hasAgenda = getAppointmentAccess(user).canViewSelf;

  return (
    <div className="@container grid min-w-0 gap-5">
      <div className={hasAgenda
        ? "grid min-w-0 items-start gap-5 @min-[58rem]:grid-cols-[minmax(0,1.3fr)_minmax(0,0.9fr)]"
        : "grid min-w-0 gap-5"}>
        <CounselorMyWork data={attention} />
        <CounselorAgenda user={user} today={today} />
      </div>

      <div className="grid min-w-0 items-start gap-5 @min-[64rem]:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <CounselorDestinations user={user} />
        <div className="grid min-w-0 gap-5">
          <HeadGuidanceDestinations user={user} />
          {summary}
        </div>
      </div>
      <OverviewAnnouncements />
    </div>
  );
}
