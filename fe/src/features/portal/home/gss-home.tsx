"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { useProjectionFocus } from "@/features/freshness/use-projection-focus";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { useGuidanceOperations } from "@/features/guidance-operations/guidance-operations-data";
import {
  AppointmentStatusBadge,
  deliveryModeLabel,
  formatAppointmentTime,
} from "@/features/appointments/appointments-shared";
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
  type AppointmentResponse,
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
          <Link
            href="/portal/work"
            className="inline-flex min-h-11 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            View all work <span aria-hidden="true" className="ml-1">→</span>
          </Link>
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
            <li key={item.id} className="grid min-w-0 gap-2 px-4 py-3.5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-4 sm:px-5">
              <div className="min-w-0 [overflow-wrap:anywhere]">
                <h3 className="font-semibold leading-6 text-ink">{row.title}</h3>
                <p className="mt-0.5 text-sm text-ink">{item.student.display_name}</p>
                {item.priority === "TIME_SENSITIVE" ? <p className="mt-0.5 text-xs font-semibold text-muted">Time sensitive</p> : null}
                <p className="mt-0.5 text-sm leading-6 text-muted">{row.detail}</p>
              </div>
              <Link
                href={row.href}
                className="inline-flex min-h-11 min-w-0 items-center self-start rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:justify-self-end [overflow-wrap:anywhere]"
              >
                {row.actionLabel} <span aria-hidden="true" className="ml-1 shrink-0">→</span>
              </Link>
            </li>
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

function ManagedAppointmentRow({ appointment }: { appointment: AppointmentResponse }) {
  return (
    <li className="min-w-0 px-4 py-3.5 sm:px-5">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <p className="font-semibold tabular-nums text-ink">
          <time dateTime={appointment.starts_at}>{formatAppointmentTime(appointment.starts_at)}</time>
          <span aria-hidden="true">–</span>
          <time dateTime={appointment.ends_at}>{formatAppointmentTime(appointment.ends_at)}</time>
          <span className="sr-only"> Philippine Time</span>
        </p>
        <AppointmentStatusBadge status={appointment.status} />
      </div>
      <h3 className="mt-1 min-w-0 [overflow-wrap:anywhere] text-base font-semibold leading-6">
        <Link
          href={`/portal/appointments/${appointment.id}`}
          aria-label={`Open managed appointment with ${appointment.student.display_name}`}
          className="flex min-h-11 w-full min-w-0 items-center text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus [overflow-wrap:anywhere]"
        >
          {appointment.student.display_name}
        </Link>
      </h3>
      <p className="mt-0.5 min-w-0 [overflow-wrap:anywhere] text-sm leading-6 text-muted">
        {appointment.service.name} <span aria-hidden="true">·</span> {deliveryModeLabel(appointment.delivery_mode)}
      </p>
      <p className="mt-0.5 min-w-0 [overflow-wrap:anywhere] text-sm leading-6 text-muted">
        Counselor: {appointment.provider.display_name}
      </p>
    </li>
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
    <Panel aria-labelledby="gss-schedule-heading">
      <PanelHeader
        title="Today's managed Appointments"
        titleId="gss-schedule-heading"
        actions={page || !initialError ? (
          <Link
            href={todayHref}
            className="inline-flex min-h-11 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            View full schedule <span aria-hidden="true" className="ml-1">→</span>
          </Link>
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

      {items.length > 0 ? <ul className="divide-y divide-border">{items.map((appointment) => <ManagedAppointmentRow key={appointment.id} appointment={appointment} />)}</ul> : null}
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
    <Panel className="border-0 bg-transparent" aria-labelledby="gss-operations-heading">
      <PanelHeader className="border-border px-0 sm:px-0" title="Office workload" titleId="gss-operations-heading" />
      <p className="py-3 text-sm leading-6 text-muted">Counts reflect office demand within your scope, not individual assignments.</p>

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
        <dl aria-label="Scoped office workload metrics" className="divide-y divide-border">
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
      {data ? <p className="border-t border-border py-2.5 text-xs text-muted">Updated <time dateTime={data.generated_at}>{formatInstitutionalDateTime(data.generated_at)}</time></p> : null}
    </Panel>
  );
}

function OfficeDestinations({ user }: { user: UserSummary }) {
  const destinations = getGssHomeDestinations(user);
  if (destinations.length === 0) return null;
  return (
    <Panel className="@container border-0 bg-transparent" aria-labelledby="gss-destinations-heading">
      <PanelHeader className="border-border px-0 sm:px-0" title="Continue in your workspaces" titleId="gss-destinations-heading" />
      <ul className="grid @min-[32rem]:grid-cols-2">
        {destinations.map((destination) => {
          const Icon = destination.icon;
          return (
            <li key={destination.href} className="border-b border-border">
              <Link
                href={destination.href}
                className="group flex min-h-11 min-w-0 items-center justify-between gap-3 py-3 pr-4 text-sm transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus"
              >
                <span className="flex min-w-0 items-start gap-3 [overflow-wrap:anywhere]">
                  <Icon aria-hidden="true" className="mt-1 h-4 w-4 shrink-0 text-brand" />
                  <span className="min-w-0">
                    <span className="block font-semibold text-brand group-hover:underline">{destination.label}</span>
                  </span>
                </span>
                <ArrowRight aria-hidden="true" className="h-4 w-4 shrink-0" />
              </Link>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

export function GssHome({ user, attention, now }: { user: UserSummary; attention: OverviewAttentionData; now: Date }) {
  const today = institutionalDateInputValue(now);
  const hasManagedSchedule = getAppointmentAccess(user).canManage;
  return (
    <div className="@container grid min-w-0 gap-5">
      <div className={hasManagedSchedule
        ? "grid min-w-0 items-start gap-5 @min-[58rem]:grid-cols-[minmax(0,1.3fr)_minmax(19rem,0.7fr)]"
        : "grid min-w-0 items-start gap-5 @min-[58rem]:grid-cols-[minmax(0,1fr)_minmax(19rem,0.7fr)]"}>
        <div className="grid min-w-0 gap-5">
          <WorkPreview user={user} data={attention} />
          {hasManagedSchedule ? <ManagedSchedule user={user} today={today} /> : null}
        </div>
        <div className="grid min-w-0 gap-5">
          <GuidanceOperationsSnapshot user={user} />
          <OfficeDestinations user={user} />
        </div>
      </div>
      <OverviewAnnouncements />
    </div>
  );
}
