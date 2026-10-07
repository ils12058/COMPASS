"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ECounselingHelp } from "@/features/ecounseling/session-help";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Notice } from "@/components/ui/notice";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { AppointmentStatusBadge, formatAppointmentDateTime } from "@/features/appointments/appointments-shared";
import { CounselingContextPanel } from "@/features/counseling/counseling-workspace";
import { RecordEncounterDialog } from "@/features/counseling/record-encounter-dialog";
import { type EncounterOriginPreset } from "@/features/counseling/record-encounter-form";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { CounselorMediaControls } from "@/features/ecounseling/counselor-media-controls";
import { getECounselingAccess } from "@/features/ecounseling/ecounseling-access";
import { ecounselingErrorMessage, hasLiveOrTransitionalMedia } from "@/features/ecounseling/ecounseling-shared";
import { SessionStage, useSessionJoin } from "@/features/ecounseling/session-stage";
import { StudentConsentPanel } from "@/features/ecounseling/student-consent-panel";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { routineEvaluationStatusLabel, routineIntakeStatusLabel } from "@/features/routine-interviews/routine-interviews-shared";
import type { AppointmentWorkspaceSummary, CounselorWorkspaceResponse, ProviderReadiness } from "@/lib/api/generated/model";
import { CounselingContextAnchorType, CounselingEntryMode, DeliveryMode, ECounselingJoinState } from "@/lib/api/generated/model";
import {
  getCounselingContextGetOverviewQueryKey,
  getCounselingListMyEncountersQueryKey,
  useCounselingContextGetOverview,
} from "@/lib/api/generated/counseling/counseling";
import { getRoutineInterviewsListEncounterCandidatesQueryKey } from "@/lib/api/generated/routine-interviews/routine-interviews";
import {
  getECounselingGetAssignedWorkspaceQueryKey,
  useECounselingGetAssignedWorkspace,
  useECounselingGetMyWorkspace,
} from "@/lib/api/generated/e-counseling/e-counseling";

// The session workspace is a container: it becomes two columns, with the session stage kept in view,
// only when the workspace itself (not the window) is wide enough for both the video and the work
// beside it. The portal dock's width is already accounted for.
// The Counselor's working area carries the Student context and the session's records, so it gets
// the wider column; a Student's holds only media consent, so the video gets more room.
const sessionLayout = {
  counselor: "grid items-start gap-5 @5xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]",
  student: "grid items-start gap-5 @5xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]",
};
const stickyStage = "@5xl:sticky @5xl:top-4";

function RecordStatus({ workspace, canManage }: { workspace: CounselorWorkspaceResponse; canManage: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const preset: EncounterOriginPreset = {
    entryMode: CounselingEntryMode.APPOINTMENT,
    appointmentId: workspace.appointment.id,
    appointmentReference: workspace.appointment.reference_code,
    studentName: workspace.student.display_name,
    deliveryMode: DeliveryMode.ONLINE,
  };

  async function handleCreated() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getECounselingGetAssignedWorkspaceQueryKey(workspace.appointment.id) }),
      queryClient.invalidateQueries({ queryKey: getCounselingListMyEncountersQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getCounselingContextGetOverviewQueryKey(CounselingContextAnchorType.APPOINTMENT, workspace.appointment.id) }),
      ...(workspace.routine_interview ? [queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListEncounterCandidatesQueryKey(workspace.routine_interview.id) })] : []),
    ]);
    setOpen(false);
  }

  if (workspace.counseling_encounter?.recorded) {
    return (
      <Panel aria-labelledby="e-counseling-encounter-heading">
        <PanelHeader title="Counseling Encounter" titleId="e-counseling-encounter-heading" />
        <PanelMessage action={<Link className={buttonVariants({ variant: "secondary" })} href={`/portal/counseling/encounters/${workspace.counseling_encounter.id}`}>View encounter</Link>}>
          Encounter recorded.
        </PanelMessage>
      </Panel>
    );
  }

  return (
    <Panel aria-labelledby="e-counseling-encounter-heading">
      <PanelHeader title="Counseling Encounter" titleId="e-counseling-encounter-heading" />
      <PanelBody>
        <p className="text-sm leading-6 text-muted">Not recorded</p>
        {canManage ? (
          <Button className="mt-3" disabled={uncertain} onClick={() => setOpen(true)}>
            {uncertain ? "Recording result unconfirmed" : "Record encounter"}
          </Button>
        ) : null}
        {canManage ? <RecordEncounterDialog open={open} onOpenChange={setOpen} preset={preset} onUncertain={() => setUncertain(true)} onCreated={handleCreated} /> : null}
      </PanelBody>
    </Panel>
  );
}

// Who the session is with, when it is, which Appointment it belongs to, and its linked Routine
// Interview. Readiness to join sits with the session stage.
function SessionHeader({
  appointmentId,
  participant,
  appointment,
  routine,
}: {
  appointmentId: string;
  participant: string;
  appointment: AppointmentWorkspaceSummary;
  routine?: { id: string; status: string } | null;
}) {
  return (
    <PageHeader
      title={participant}
      description={formatAppointmentDateTime(appointment.starts_at, appointment.ends_at)}
      meta={<AppointmentStatusBadge status={appointment.status} />}
      help={<ECounselingHelp />}
      back={(
        <GuardedPortalLink href={`/portal/appointments/${appointmentId}`} className={pageBackLinkClass}>
          ← Back to appointment
        </GuardedPortalLink>
      )}
      actions={routine ? (
        <Link className={buttonVariants({ variant: "secondary" })} href={`/portal/routine-interviews/${routine.id}`}>
          Routine Interview
        </Link>
      ) : undefined}
    >
      <p className="mt-0.5 text-sm text-muted">
        E-Counseling <span aria-hidden="true"> · </span>
        <span className="font-mono text-ink">{appointment.reference_code}</span>
      </p>
      {routine ? <p className="mt-0.5 text-sm text-muted">Routine Interview · {routine.status}</p> : null}
    </PageHeader>
  );
}

function WorkspaceSkeleton() {
  return (
    <div aria-busy="true" className="@container">
      <span className="sr-only">Loading E-Counseling session…</span>
      <Skeleton className="h-9 w-1/2" />
      <Skeleton className="mt-2 h-5 w-2/3" />
      <div className={`mt-5 ${sessionLayout.counselor}`}>
        <Skeleton className="aspect-video w-full" />
        <div className="space-y-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-56 w-full" />
        </div>
      </div>
    </div>
  );
}

function WorkspaceLoadError({ error, retry }: { error: unknown; retry: () => void }) {
  return <section className="max-w-2xl"><PageHeader title="E-Counseling unavailable" /><Notice role="alert" action={<><Button variant="secondary" onClick={retry}>Retry</Button><Link className="inline-flex min-h-10 items-center px-2 text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" href="/portal/appointments/my">Return to appointments</Link></>}>{ecounselingErrorMessage(error, "This E-Counseling session is unavailable. Try again.")}</Notice></section>;
}

const JOIN_BOUNDARY_REFRESH_BUFFER_MS = 500;
const MAX_BROWSER_TIMEOUT_MS = 2_147_000_000;

function useECounselingBoundaryRefresh(
  appointmentId: string,
  readiness: ProviderReadiness | undefined,
  refetchWorkspace: () => Promise<unknown>,
) {
  const lastTriggeredBoundaryRef = useRef<string | null>(null);

  useEffect(() => {
    const joinState = readiness?.join_state;
    const boundary =
      joinState === ECounselingJoinState.TOO_EARLY
        ? readiness?.join_available_from
        : joinState === ECounselingJoinState.OPEN
          ? readiness?.join_available_until
          : null;

    if (!joinState || !boundary) return;

    const boundaryTime = Date.parse(boundary);
    if (!Number.isFinite(boundaryTime)) return;

    const boundaryKey = `${appointmentId}:${joinState}:${boundary}`;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const schedule = () => {
      if (cancelled || lastTriggeredBoundaryRef.current === boundaryKey) return;

      const delay = boundaryTime + JOIN_BOUNDARY_REFRESH_BUFFER_MS - Date.now();
      if (delay <= 0) {
        lastTriggeredBoundaryRef.current = boundaryKey;
        void refetchWorkspace();
        return;
      }

      timer = setTimeout(schedule, Math.min(delay, MAX_BROWSER_TIMEOUT_MS));
    };

    schedule();

    return () => {
      cancelled = true;
      if (timer !== null) clearTimeout(timer);
    };
  }, [
    appointmentId,
    readiness?.join_available_from,
    readiness?.join_available_until,
    readiness?.join_state,
    refetchWorkspace,
  ]);
}

export function ECounselingWorkspace({ appointmentId }: { appointmentId: string }) {
  const { user } = usePortalSession();
  const access = getECounselingAccess(user);
  if (!access.hasWorkspace) {
    return <WorkspaceUnavailable title="E-Counseling unavailable">This session is unavailable to this account.</WorkspaceUnavailable>;
  }
  return access.isStudent
    ? <StudentWorkspace appointmentId={appointmentId} access={access} />
    : <CounselorWorkspace appointmentId={appointmentId} access={access} />;
}

function StudentWorkspace({ appointmentId, access }: { appointmentId: string; access: ReturnType<typeof getECounselingAccess> }) {
  const [localCallJoined, setLocalCallJoined] = useState(false);
  const workspace = useECounselingGetMyWorkspace(appointmentId, { query: {
    retry: false,
    refetchInterval: (query) => localCallJoined || hasLiveOrTransitionalMedia(query.state.data?.data.media) ? 7000 : false,
  } });
  const join = useSessionJoin({ appointmentId, refetchWorkspace: workspace.refetch, onCallChange: setLocalCallJoined });
  const data = workspace.data?.data;
  const media = data?.media;

  useECounselingBoundaryRefresh(appointmentId, data?.provider_readiness, workspace.refetch);

  if (workspace.isPending) return <WorkspaceSkeleton />;
  if (workspace.isError || !data || !media) return <WorkspaceLoadError error={workspace.error} retry={() => void workspace.refetch()} />;

  return (
    <div className="@container">
      <SessionHeader
        appointmentId={appointmentId}
        participant={`With ${data.counselor.display_name}`}
        appointment={data.appointment}
        routine={data.routine_interview ? { id: data.routine_interview.id, status: `${routineIntakeStatusLabel(data.routine_interview.intake_status)} Intake` } : null}
      />
      <div className={sessionLayout.student}>
        <SessionStage
          className={stickyStage}
          readiness={data.provider_readiness}
          media={media}
          canJoin={access.canJoinSelf}
          inCall={localCallJoined}
          join={join}
        />
        <div className="min-w-0">
          <StudentConsentPanel appointmentId={appointmentId} access={access} media={media} />
        </div>
      </div>
    </div>
  );
}

function CounselorWorkspace({ appointmentId, access }: { appointmentId: string; access: ReturnType<typeof getECounselingAccess> }) {
  const { user } = usePortalSession();
  const counselingAccess = getCounselingAccess(user);
  const [localCallJoined, setLocalCallJoined] = useState(false);
  const queryClient = useQueryClient();
  const workspace = useECounselingGetAssignedWorkspace(appointmentId, { query: {
    retry: false,
    refetchInterval: (query) => localCallJoined || hasLiveOrTransitionalMedia(query.state.data?.data.media) ? 7000 : false,
  } });
  const join = useSessionJoin({ appointmentId, refetchWorkspace: workspace.refetch, onCallChange: setLocalCallJoined });
  const data = workspace.data?.data;
  const media = data?.media;

  useECounselingBoundaryRefresh(appointmentId, data?.provider_readiness, workspace.refetch);
  const context = useCounselingContextGetOverview(CounselingContextAnchorType.APPOINTMENT, appointmentId, {
    query: { enabled: Boolean(data?.counseling_context_available), retry: false },
  });

  if (workspace.isPending) return <WorkspaceSkeleton />;
  if (workspace.isError || !data || !media) return <WorkspaceLoadError error={workspace.error} retry={() => void workspace.refetch()} />;

  const routine = data.routine_interview;

  return (
    <div className="@container">
      <SessionHeader
        appointmentId={appointmentId}
        participant={data.student.display_name}
        appointment={data.appointment}
        routine={routine ? { id: routine.id, status: `${routineIntakeStatusLabel(routine.intake_status)} Intake · ${routineEvaluationStatusLabel(routine.evaluation_status)} Evaluation` } : null}
      />
      <div className={sessionLayout.counselor}>
        <SessionStage
          className={stickyStage}
          readiness={data.provider_readiness}
          media={media}
          canJoin={access.canJoinAssigned}
          inCall={localCallJoined}
          join={join}
        />
        {/* The working area scrolls with the page beside the stage. Media controls come first so
            consent and capture, including stopping a capture, are always at the same place. */}
        <div className="min-w-0 space-y-5">
          <CounselorMediaControls appointmentId={appointmentId} access={access} workspace={data} />
          {!data.counseling_context_available ? (
            <Panel aria-labelledby="e-counseling-context-heading">
              <PanelHeader title="Student information" titleId="e-counseling-context-heading" />
              <PanelMessage role="status">Student information isn’t available right now.</PanelMessage>
            </Panel>
          ) : context.isPending ? (
            <Panel aria-busy="true" aria-labelledby="e-counseling-context-heading">
              <PanelHeader title="Student information" titleId="e-counseling-context-heading" />
              <PanelBody>
                <span className="sr-only">Loading Student context…</span>
                <Skeleton className="h-10 w-full" />
                <Skeleton className="mt-3 h-40 w-full" />
              </PanelBody>
            </Panel>
          ) : context.isError || !context.data?.data ? (
            <Panel aria-labelledby="e-counseling-context-heading">
              <PanelHeader title="Student information" titleId="e-counseling-context-heading" />
              <PanelMessage role="alert" action={<Button variant="secondary" onClick={() => void context.refetch()}>Retry</Button>}>
                Student information couldn’t be loaded. Try again.
              </PanelMessage>
            </Panel>
          ) : (
            <CounselingContextPanel anchorType={CounselingContextAnchorType.APPOINTMENT} anchorId={appointmentId} overview={context.data.data} access={counselingAccess} onPublished={() => void queryClient.invalidateQueries({ queryKey: getCounselingContextGetOverviewQueryKey(CounselingContextAnchorType.APPOINTMENT, appointmentId) })} />
          )}
          <RecordStatus workspace={data} canManage={counselingAccess.canManageAssigned} />
        </div>
      </div>
    </div>
  );
}
