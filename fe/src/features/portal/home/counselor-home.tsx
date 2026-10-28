"use client";

import { CalendarClock, ListChecks } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { TaskLink } from "@/components/ui/task-link";
import { SectionLink } from "@/components/ui/section-link";
import { HomeShortcuts } from "./home-shortcuts";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { HomeAgendaRow } from "./home-agenda-row";
import { OverviewAnnouncements } from "@/features/portal/home/overview-announcements";
import type { OverviewAttentionData } from "@/features/portal/home/overview-work";
import {
  getCounselorHomeDestinations,
  getHeadGuidanceHomeDestinations,
} from "@/features/portal/home/counselor-home-presentation";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { useProjectionFocus } from "@/features/freshness/use-projection-focus";
import { AppointmentListOrdering, AppointmentStatus, type UserSummary } from "@/lib/api/generated/model";
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
    <Panel className="@container/agenda" aria-labelledby="counselor-agenda-heading">
      <PanelHeader
        className="border-b-0"
        title={<span className="[overflow-wrap:anywhere]">{"Today's appointments"}</span>}
        titleId="counselor-agenda-heading"
        description={INSTITUTION_TIME_ZONE_LABEL}
        actions={(
          <SectionLink href={todayHref} label="Schedule" accessibleLabel="View today’s schedule" icon={CalendarClock} />
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
            {items.map((appointment) => <HomeAgendaRow key={appointment.id} appointment={appointment} />)}
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

function CounselorMyWork({ data }: { data: OverviewAttentionData }) {
  const initialError = data.items.some((item) => item.id === "work-unavailable");

  return (
    <Panel aria-labelledby="counselor-work-heading">
      <PanelHeader
        title="My work"
        titleId="counselor-work-heading"
        actions={data.viewAllWork && !initialError ? (
          <SectionLink href="/portal/work" label="All work" accessibleLabel="View all work" icon={ListChecks} />
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
            >
              <TaskLink href={item.href} actionLabel={item.actionLabel} title={item.title} subject={item.subject} detail={item.detail} priority={item.priorityLabel} />
              {item.onRetry ? <div className="px-4 pb-3 sm:px-5"><Button variant="secondary" onClick={item.onRetry}>Retry</Button></div> : null}
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
  return <HomeShortcuts title="Continue in your workspace" titleId="counselor-continuation-heading" destinations={destinations} />;
}

function HeadGuidanceDestinations({ user }: { user: UserSummary }) {
  const destinations = getHeadGuidanceHomeDestinations(user);
  if (destinations.length === 0) return null;
  return <HomeShortcuts title="Authorized oversight" titleId="head-guidance-oversight-heading" destinations={destinations} />;
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
      <CounselorMyWork data={attention} />
      <div className={hasAgenda ? "grid min-w-0 items-start gap-5 @min-[52rem]:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]" : "grid min-w-0 gap-5"}>
        <CounselorAgenda user={user} today={today} />
        <div className="grid min-w-0 gap-5">
          <CounselorDestinations user={user} />
          {summary}
        </div>
      </div>
      <HeadGuidanceDestinations user={user} />
      <OverviewAnnouncements />
    </div>
  );
}
