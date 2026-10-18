"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { GroupSessionsHeading, groupSessionsError } from "./group-sessions-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { canBrowseGroupSessions } from "./group-sessions-access";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { Panel, PanelBody, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { formatAppointmentDateTime } from "@/features/appointments/appointments-shared";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import { useGroupSessionsGetMyRegistrations } from "@/lib/api/generated/group-sessions/group-sessions";

function registrationStatusLabel(status: string): string {
  if (status === "REGISTERED") return "Registered";
  if (status === "CANCELLED") return "Cancelled";
  return "Status unavailable";
}

export function GroupSessionsHistoryPage() {
  const { user } = usePortalSession();
  const allowed = canBrowseGroupSessions(user);
  const registrations = useGroupSessionsGetMyRegistrations({ query: { retry: false, enabled: allowed } });
  const rows = registrations.data?.data ?? [];

  if (!allowed) return <WorkspaceUnavailable title="Group Sessions unavailable">You don’t have access to Student registrations.</WorkspaceUnavailable>;

  return (
    <>
      <GroupSessionsHeading />

      <Panel aria-labelledby="my-group-sessions-heading">
        <PanelHeader
          title="Registrations"
          titleId="my-group-sessions-heading"
          context={registrations.isFetching && !registrations.isPending ? "Refreshing…" : undefined}
        />
        {registrations.isPending ? (
          <PanelBody className="space-y-3" aria-label="Loading group session registrations">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </PanelBody>
        ) : registrations.isError ? (
          <PanelMessage
            role="alert"
            tone="danger"
            action={
              <Button variant="secondary" onClick={() => void registrations.refetch()}>
                Retry
              </Button>
            }
          >
            {groupSessionsError(registrations.error, "Your group session registrations could not be loaded. Try again.")}
          </PanelMessage>
        ) : rows.length === 0 ? (
          <PanelMessage>You have no group session registrations yet.</PanelMessage>
        ) : (
          <div className="divide-y divide-brand-line">
            {rows.map((registration) => (
              <article key={registration.id} className="px-4 py-4 sm:px-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="font-semibold text-ink">
                      <Link
                        className="underline decoration-brand-line underline-offset-4 hover:decoration-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                        href={`/portal/group-sessions/${registration.session_id}`}
                      >
                        {registration.session_title}
                      </Link>
                    </h3>
                    <p className="mt-1 text-sm text-muted">
                      {formatAppointmentDateTime(registration.starts_at, registration.ends_at)}
                    </p>
                    <p className="mt-1 text-xs text-muted">
                      Registered {registration.registered_at ? formatInstitutionalDateTime(registration.registered_at) : "date unavailable"}
                    </p>
                  </div>
                  <span className="inline-flex min-h-6 items-center rounded-full border border-border bg-surface-muted px-2.5 text-xs font-semibold text-muted">
                    {registrationStatusLabel(registration.status)}
                  </span>
                </div>
                {registration.cancellation_reason ? (
                  <p className="mt-2 text-sm text-muted">Reason: {registration.cancellation_reason}</p>
                ) : null}
                {registration.attended !== null ? (
                  <p className="mt-2 text-sm text-muted">
                    Attendance: {registration.attended ? "Attended" : "Not marked present"}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </Panel>
    </>
  );
}
