"use client";

import Link from "next/link";
import { TaskLink } from "@/components/ui/task-link";
import { SectionLink } from "@/components/ui/section-link";
import { HomeShortcuts } from "./home-shortcuts";
import { HomeAgendaRow } from "./home-agenda-row";
import { CalendarClock, ListChecks } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { useProjectionFocus } from "@/features/freshness/use-projection-focus";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { useGuidanceOperations } from "@/features/guidance-operations/guidance-operations-data";
import { OverviewAnnouncements } from "@/features/portal/home/overview-announcements";
import type { OverviewAttentionData } from "@/features/portal/home/overview-work";
import {
  GSS_HOME_PREVIEW_SIZE,
  getGssHomeDestinations,
  getGssManagedAppointmentParams,
  presentGssOperations,
  presentGssWork,
} from "@/features/portal/home/gss-home-presentation";
import { CompassApiError } from "@/lib/api/errors";
import { formatInstitutionalDateTime, institutionalDateInputValue } from "@/lib/institutional-time";
import {
  AppointmentStatus,
  type UserSummary,
} from "@/lib/api/generated/model";
import {
  getAppointmentsListManagedQueryKey,
  useAppointmentsListManaged,
} from "@/lib/api/generated/appointments/appointments";

const appointmentsManagedQueryFamily = getAppointmentsListManagedQueryKey();

function isAuthorizationFailure(error: unknown): boolean {
  return error instanceof CompassApiError && (error.status === 401 || error.status === 403);
}

function workErrorMessage(error: unknown): string {
  if (error instanceof CompassApiError && error.status === 403) return "You don't have access to My work.";
  if (error instanceof CompassApiError && error.status === 401) return "Your session has ended. Sign in again to view My work.";
  return "My work could not be loaded. Try again.";
}

function appointmentErrorMessageForGss(error: unknown): string {
  if (error instanceof CompassApiError && error.status === 403) return "Managed Appointments are not available for this account.";
  if (error instanceof CompassApiError && error.status === 401) return "Your session has ended. Sign in again to view managed Appointments.";
  return "Today's managed Appointments could not be loaded. Try again.";
}

function WorkPreview({ user, data }: { user: UserSummary; data: OverviewAttentionData }) {
  const initialError = data.workIsError && !data.workHasConfirmedData;
  const accessDenied = isAuthorizationFailure(data.workError);
  const items = data.canonicalWorkItems.flatMap((item) => {
    const row = presentGssWork(item, user, data.workGeneratedAt);
    return row ? [{ item, row }] : [];
  });

  return (
    <Panel aria-labelledby="gss-work-heading">
      <PanelHeader
        title="My work"
        titleId="gss-work-heading"
        actions={!accessDenied ? (
          <SectionLink href="/portal/work" label="All work" accessibleLabel="View all work" icon={ListChecks} />
        ) : undefined}
      />

      {data.workIsError && data.workHasConfirmedData ? (
        <RefreshFailureNotice
          message="My work could not be refreshed. Showing the last confirmed items."
          onRetry={() => data.retryWork?.()}
        />
      ) : null}

      {initialError ? (
        <Notice role="alert" tone="warning" action={data.retryWork ? (
          <Button variant="secondary" onClick={data.retryWork}>Retry</Button>
        ) : undefined}>
          {workErrorMessage(data.workError)}
        </Notice>
      ) : null}

      {items.length > 0 ? (
        <ul className="divide-y divide-border">
          {items.map(({ item, row }) => (
            <li key={item.id}><TaskLink href={row.href} actionLabel={row.actionLabel} title={row.title} subject={item.student.display_name} detail={row.detail} priority={item.priority === "TIME_SENSITIVE" ? "Time sensitive" : undefined} /></li>
          ))}
        </ul>
      ) : data.workIsPending && !data.workHasConfirmedData ? (
        <div aria-busy="true" className="space-y-3 px-4 py-4 sm:px-5">
          <Skeleton className="h-4 w-44" />
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
          <p className="sr-only">Loading My work…</p>
        </div>
      ) : data.workHasConfirmedData && data.canonicalWorkItems.length === 0 ? (
        <PanelMessage>
          {data.workIsError ? "The last confirmed My work projection had no items." : "No items currently need attention in My work."}
        </PanelMessage>
      ) : data.workHasConfirmedData ? (
        <PanelMessage>No authorized work items are available to show in this Home preview.</PanelMessage>
      ) : null}

      {data.workHasConfirmedData && data.workHasNext ? (
        <PanelMessage>Showing the first {data.workPageSize ?? GSS_HOME_PREVIEW_SIZE} items. More work is available in the full queue.</PanelMessage>
      ) : null}

      {data.workHasConfirmedData && data.workGeneratedAt ? (
        <p className="border-t border-border px-4 py-2.5 text-xs text-muted sm:px-5">
          Queue updated <time dateTime={data.workGeneratedAt}>{formatInstitutionalDateTime(data.workGeneratedAt)}</time>
        </p>
      ) : null}
    </Panel>
  );
}

function ManagedSchedule({ user, today }: { user: UserSummary; today: string }) {
  const access = getAppointmentAccess(user);
  const params = getGssManagedAppointmentParams(today);
  const query = useAppointmentsListManaged(params, {
    query: {
      enabled: access.canManage,
      retry: false,
      refetchInterval: 60_000,
      refetchIntervalInBackground: false,
      refetchOnWindowFocus: "always",
      refetchOnReconnect: "always",
    },
  });
  useProjectionFocus(appointmentsManagedQueryFamily, access.canManage);

  if (!access.canManage) return null;

  const page = safeQueryData(query)?.data;
  const items = page?.items.filter((appointment) => appointment.status === AppointmentStatus.SCHEDULED) ?? [];
  const todayHref = `/portal/appointments/manage?status=${AppointmentStatus.SCHEDULED}&from=${today}&to=${today}`;
  const initialError = query.isError && !page;

  return (
    <Panel className="@container/agenda" aria-labelledby="gss-schedule-heading">
      <PanelHeader
        title="Today's managed Appointments"
        titleId="gss-schedule-heading"
        actions={page || !initialError ? (
          <SectionLink href={todayHref} label="Schedule" accessibleLabel="View full schedule" icon={CalendarClock} />
        ) : undefined}
      />

      {query.isError && page ? (
        <RefreshFailureNotice
          message="Today's managed Appointments could not be refreshed. Showing the last confirmed schedule."
          onRetry={() => void query.refetch()}
          retrying={query.isFetching}
        />
      ) : null}
      {initialError ? (
        <Notice role="alert" tone="warning" action={<Button variant="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>Retry</Button>}>
          {appointmentErrorMessageForGss(query.error)}
        </Notice>
      ) : null}

      {items.length > 0 ? <ul className="divide-y divide-border">{items.map((appointment) => <HomeAgendaRow key={appointment.id} appointment={appointment} managed />)}</ul> : null}
      {query.isPending && !page ? (
        <div aria-busy="true" className="space-y-3 px-4 py-4 sm:px-5">
          <Skeleton className="h-4 w-44" />
          <Skeleton className="h-4 w-2/3" />
          <p className="sr-only">{"Loading today's managed Appointments…"}</p>
        </div>
      ) : null}
      {page && items.length === 0 ? (
        <PanelMessage>
          {query.isError ? "The last confirmed result showed no scheduled managed Appointments today." : "No scheduled managed Appointments today."}
        </PanelMessage>
      ) : null}
      {page?.has_next ? <PanelMessage>Showing the first {GSS_HOME_PREVIEW_SIZE} scheduled Appointments. Open the full schedule to see more.</PanelMessage> : null}
      {page ? <p className="border-t border-border px-4 py-2.5 text-xs text-muted sm:px-5">Times shown in Philippine Time.</p> : null}
    </Panel>
  );
}

function GuidanceOperationsSnapshot({ user }: { user: UserSummary }) {
  const query = useGuidanceOperations(user);
  const data = safeQueryData(query)?.data;
  const metrics = data ? presentGssOperations(data, user) : null;
  const initialError = query.isError && !data;
  const accessDenied = isAuthorizationFailure(query.error);
  const allZero = Boolean(metrics?.length) && metrics?.every((metric) => metric.count === 0);

  return (
    <Panel aria-labelledby="gss-operations-heading">
      <PanelHeader className="border-b-0 pb-1" title="Office workload" titleId="gss-operations-heading" />
      <p className="px-4 pb-3 text-sm leading-6 text-muted sm:px-5">Counts reflect office demand within your scope, not individual assignments.</p>

      {query.isError && data ? (
        <RefreshFailureNotice
          message="Guidance Operations could not be refreshed. Showing the last confirmed office workload."
          onRetry={() => void query.refetch()}
          retrying={query.isFetching}
        />
      ) : null}
      {initialError ? (
        <Notice role="alert" tone="warning" action={<Button variant="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>Retry</Button>}>
          {accessDenied ? "Guidance Operations are not available for this account." : "Office workload could not be loaded. Try again."}
        </Notice>
      ) : null}
      {query.isPending && !data ? (
        <div aria-busy="true" className="space-y-3 px-4 py-4 sm:px-5">
          <Skeleton className="h-4 w-44" />
          <Skeleton className="h-4 w-2/3" />
          <p className="sr-only">Loading office workload…</p>
        </div>
      ) : null}

      {metrics && metrics.length > 0 ? (
        <dl aria-label="Scoped office workload metrics" className="divide-y divide-border px-4 sm:px-5">
          {metrics.map((metric) => (
            <div key={metric.key} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-start gap-x-4 py-3">
              <dt className="min-w-0 text-sm font-semibold leading-6 [overflow-wrap:anywhere]">
                {metric.href ? <Link className="inline-flex min-h-11 items-center rounded-sm text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" href={metric.href}>{metric.label}</Link> : <span className="block py-2.5">{metric.label}</span>}
                {metric.oldest ? <span className="mt-0.5 block text-sm font-normal leading-6 text-muted">{metric.oldest.label}: <time dateTime={metric.oldest.instant}>{formatInstitutionalDateTime(metric.oldest.instant)}</time></span> : null}
              </dt>
              <dd className="py-2.5 text-base font-semibold tabular-nums text-ink">{metric.count.toLocaleString()}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {metrics && metrics.length === 0 ? <PanelMessage>No Guidance Operations metrics are available within the returned scope.</PanelMessage> : null}
      {allZero ? <PanelMessage>{query.isError ? "The last confirmed office workload had no items waiting." : "No work is currently waiting in the returned office metrics."}</PanelMessage> : null}
      {data ? <p className="border-t border-border px-4 py-2.5 text-xs text-muted sm:px-5">Updated <time dateTime={data.generated_at}>{formatInstitutionalDateTime(data.generated_at)}</time></p> : null}
    </Panel>
  );
}

function OfficeDestinations({ user }: { user: UserSummary }) {
  const destinations = getGssHomeDestinations(user);
  if (destinations.length === 0) return null;
  return <HomeShortcuts title="Continue in your workspaces" titleId="gss-destinations-heading" destinations={destinations}
    illustration={destinations.some(item => item.href === "/portal/appointments") ? "/illustrations/appointment-calendar-3d.png" : undefined} />;
}

export function GssHome({ user, attention, now }: { user: UserSummary; attention: OverviewAttentionData; now: Date }) {
  const today = institutionalDateInputValue(now);
  const hasManagedSchedule = getAppointmentAccess(user).canManage;
  return <div className="@container grid min-w-0 gap-5">
    <WorkPreview user={user} data={attention} />
    <div className={hasManagedSchedule ? "grid min-w-0 items-start gap-5 @min-[52rem]:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]" : "grid min-w-0 gap-5"}>
      {hasManagedSchedule ? <ManagedSchedule user={user} today={today} /> : null}
      <div className="grid min-w-0 gap-5">
        <GuidanceOperationsSnapshot user={user} />
        <OfficeDestinations user={user} />
      </div>
    </div>
    <OverviewAnnouncements />
  </div>;
}
