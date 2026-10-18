"use client";

import Link from "next/link";

import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader, PanelMessage, PanelSection } from "@/components/ui/panel";
import { GroupSessionsHelp, GroupSessionsNavigation, groupSessionsError } from "./group-sessions-shared";
import { Skeleton } from "@/components/ui/skeleton";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { formatAppointmentDateTime } from "@/features/appointments/appointments-shared";
import { useGroupSessionsGetDetail } from "@/lib/api/generated/group-sessions/group-sessions";

function sessionStatusLabel(status: string): string {
  switch (status) {
    case "PUBLISHED":
      return "Published";
    case "CANCELLED":
      return "Cancelled";
    case "COMPLETED":
      return "Completed";
    case "DRAFT":
      return "Draft";
    default:
      return "Status unavailable";
  }
}

export function GroupSessionDetailPage({ sessionId }: { sessionId: string }) {
  const { user } = usePortalSession();
  const sessionQuery = useGroupSessionsGetDetail(sessionId, { query: { retry: false } });
  const session = sessionQuery.data?.data;
  const isStudent = user.role === "STUDENT";

  if (sessionQuery.isPending) {
    return (
      <>
        <PageHeader title="Group session details" />
        <Panel>
          <PanelBody className="space-y-3" aria-label="Loading group session details">
            <Skeleton className="h-8 w-2/5" />
            <Skeleton className="h-28 w-full" />
          </PanelBody>
        </Panel>
      </>
    );
  }

  if (sessionQuery.isError || !session) {
    return (
      <>
        <PageHeader title="Group session details" />
        <PanelMessage
          role="alert"
          tone="danger"
          action={
            <button
              type="button"
              className="min-h-10 rounded-md border border-border-strong bg-surface-raised px-4 text-sm font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              onClick={() => void sessionQuery.refetch()}
            >
              Retry
            </button>
          }
        >
          {groupSessionsError(sessionQuery.error, "The group session details could not be loaded. Try again.")}
        </PanelMessage>
      </>
    );
  }

  const backHref = isStudent ? "/portal/group-sessions/my" : "/portal/group-sessions/manage";
  const backLabel = isStudent ? "My Registrations" : "Manage Sessions";

  return (
    <>
      <PageHeader
        title={session.title}
        help={<GroupSessionsHelp />}
        description={session.description || undefined}
        back={
          <Link
            href={backHref}
            className={pageBackLinkClass}
          >
            Back to {backLabel}
          </Link>
        }
        meta={
          <span className="inline-flex min-h-6 items-center rounded-full border border-border bg-surface-muted px-2.5 text-xs font-semibold text-muted">
            {sessionStatusLabel(session.status)}
          </span>
        }
      />

      <GroupSessionsNavigation />
      <Panel aria-labelledby="group-session-details-heading">
        <PanelHeader title="Event details" titleId="group-session-details-heading" />
        <PanelSection title="Schedule and place" titleId="group-session-schedule-heading">
          <dl className="grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Date and time</dt>
              <dd className="mt-1 text-sm text-ink">
                {formatAppointmentDateTime(session.starts_at, session.ends_at)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Service</dt>
              <dd className="mt-1 text-sm text-ink">{session.service_name}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Delivery</dt>
              <dd className="mt-1 text-sm text-ink">
                {session.delivery_mode === "ONLINE" ? "Online" : "In person"}
              </dd>
            </div>
            {session.venue_or_meeting_url ? (
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                  {session.delivery_mode === "ONLINE" ? "Meeting details" : "Location"}
                </dt>
                <dd className="mt-1 break-words text-sm text-ink">{session.venue_or_meeting_url}</dd>
              </div>
            ) : null}
          </dl>
        </PanelSection>

        <PanelSection title="Facilitators" titleId="group-session-facilitators-heading">
          {session.facilitators.length ? (
            <ul className="space-y-2">
              {session.facilitators.map((facilitator) => (
                <li key={facilitator.id} className="text-sm text-ink">
                  {facilitator.display_name}
                  {facilitator.is_lead ? " · Lead facilitator" : ""}
                  {facilitator.kind === "EXTERNAL" ? " · Guest speaker" : ""}
                  {!facilitator.is_current ? " · Former facilitator" : ""}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">Facilitator details are not available.</p>
          )}
        </PanelSection>

        {session.status === "CANCELLED" && session.cancellation_reason ? (
          <PanelSection title="Cancellation" titleId="group-session-cancellation-heading">
            <p className="text-sm text-muted">{session.cancellation_reason}</p>
          </PanelSection>
        ) : null}
      </Panel>
    </>
  );
}
