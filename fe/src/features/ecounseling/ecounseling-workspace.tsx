"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button, buttonVariants } from "@/components/ui/button";
import { DisclosureSection } from "@/components/ui/disclosure";
import { Notice } from "@/components/ui/notice";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { AppointmentStatusBadge, formatAppointmentDateTime } from "@/features/appointments/appointments-shared";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { CounselingContextPanel } from "@/features/counseling/counseling-workspace";
import { RecordEncounterDialog } from "@/features/counseling/record-encounter-dialog";
import { type EncounterOriginPreset } from "@/features/counseling/record-encounter-form";
import { CallStage } from "@/features/ecounseling/call/call-stage";
import { useActiveECounselingCall } from "@/features/ecounseling/runtime/active-call-context";
import { useSessionCallView } from "@/features/ecounseling/runtime/use-session-call-view";
import { CaptureStartDialogs, CounselorMediaStrip, GovernedCaptureControls, useCounselorMedia } from "@/features/ecounseling/counselor-media";
import { getECounselingAccess, type ECounselingAccess } from "@/features/ecounseling/ecounseling-access";
import { captureStatusLabel, ecounselingErrorMessage, sessionRefreshInterval } from "@/features/ecounseling/ecounseling-shared";
import { ECounselingHelp } from "@/features/ecounseling/session-help";
import { SessionFiles } from "@/features/ecounseling/session-files";
import { LayoutPresetControl, phoneBleed, sessionGrid, sessionStageClass, useWideWorkspace, type LayoutPreset } from "@/features/ecounseling/session-layout";
import { StudentConsentPanel } from "@/features/ecounseling/student-consent-panel";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { GuidanceContextualMessages, GuidanceMessagesTrigger } from "@/features/guidance-messages/guidance-contextual-messages";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { routineEvaluationStatusLabel, routineIntakeStatusLabel } from "@/features/routine-interviews/routine-interviews-shared";
import type { AppointmentWorkspaceSummary, CounselorWorkspaceResponse, MediaWorkspaceState, ProviderReadiness, StudentWorkspaceResponse } from "@/lib/api/generated/model";
import { CounselingContextAnchorType, CounselingEntryMode, DeliveryMode, ECounselingCaptureStatus, ECounselingJoinState } from "@/lib/api/generated/model";
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
import { cn } from "@/lib/utils/cn";


// Who the session is with, its status and time. The Appointment reference and the Routine Interview
// sit under Session details, lower on the page.
function SessionHeader({
  appointmentId,
  participant,
  appointment,
  mediaPolicyVersion,
  layoutControl,
}: {
  appointmentId: string;
  participant: string;
  appointment: AppointmentWorkspaceSummary;
  mediaPolicyVersion: MediaWorkspaceState["media_policy_version"];
  // Shown beside the title only where the workspace is wide enough for presets to change anything.
  layoutControl?: ReactNode;
}) {
  return (
    <PageHeader
      title={participant}
      meta={<AppointmentStatusBadge status={appointment.status} />}
      // Guidance Messages is the session's durable text channel (ADR-103); there is no call chat.
      actions={<div className="flex flex-wrap items-start gap-2"><GuidanceMessagesTrigger />{layoutControl}</div>}
      help={<ECounselingHelp mediaPolicyVersion={mediaPolicyVersion} />}
      back={(
        <GuardedPortalLink href={`/portal/appointments/${appointmentId}`} className={pageBackLinkClass}>
          Back to appointment
        </GuardedPortalLink>
      )}
    >
      <p className="mt-1 text-sm text-muted">
        {formatAppointmentDateTime(appointment.starts_at, appointment.ends_at)}
        <span aria-hidden="true"> · </span>
        <span className="whitespace-nowrap">E-Counseling</span>
      </p>
    </PageHeader>
  );
}

function SessionDetails({ appointment, routine, media }: {
  appointment: AppointmentWorkspaceSummary;
  routine?: { id: string; status: string } | null;
  // A Student sees what was captured here; the Counselor sees it under Session files.
  media?: MediaWorkspaceState;
}) {
  const captured = media
    ? ([
        ["Recording", media.recording.capture_status, media.recording.artifact_disposed_at],
        ["Transcription", media.transcription.capture_status, media.transcription.artifact_disposed_at],
      ] as const).filter(([, status]) => status !== ECounselingCaptureStatus.NOT_STARTED)
    : [];
  return (
    <DisclosureSection title="Session details" status={<span className="font-mono">{appointment.reference_code}</span>}>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-2 px-1 text-sm">
        <dt className="text-muted">Appointment</dt>
        <dd className="font-mono text-ink">{appointment.reference_code}</dd>
        {routine ? (
          <>
            <dt className="text-muted">Routine Interview</dt>
            <dd className="text-ink">
              {routine.status}
              <span aria-hidden="true"> · </span>
              <Link className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" href={`/portal/routine-interviews/${routine.id}`}>Open Routine Interview</Link>
            </dd>
          </>
        ) : null}
        {captured.map(([label, status, disposedAt]) => (
          <div key={label} className="contents">
            <dt className="text-muted">{label}</dt>
            <dd className="text-ink">{disposedAt ? "Deleted under an approved retention rule" : captureStatusLabel(status)}</dd>
          </div>
        ))}
      </dl>
    </DisclosureSection>
  );
}

function WorkspaceSkeleton() {
  return (
    <div aria-busy="true" className="@container">
      <span className="sr-only">Loading E-Counseling session…</span>
      <Skeleton className="h-5 w-32" />
      <Skeleton className="mt-3 h-9 w-1/2" />
      <Skeleton className="mt-2 h-5 w-2/3" />
      <div className={cn("mt-5 grid items-start gap-5", sessionGrid.balanced)}>
        <Skeleton className="aspect-video w-full" />
        <div className="space-y-3">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
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

// Re-reads the session when the join window opens or closes, so Join appears or disappears on time.
// The backend still decides every join.
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
    return <WorkspaceUnavailable title="E-Counseling unavailable">This session is unavailable.</WorkspaceUnavailable>;
  }
  return access.isStudent
    ? <StudentWorkspace appointmentId={appointmentId} access={access} />
    : <CounselorWorkspace appointmentId={appointmentId} access={access} />;
}

// While this Appointment has the portal's live call, the portal runtime keeps its session state
// fresh through the same query, so the page adds no second poll (ADR-094). Otherwise the page
// refreshes while something is being captured or prepared. A failed refresh keeps the last confirmed
// session on screen.
function usePagePolling(appointmentId: string) {
  const runtime = useActiveECounselingCall();
  const runtimePolls = runtime.appointmentId === appointmentId && runtime.live;
  return (media: MediaWorkspaceState | undefined) => (runtimePolls ? false : sessionRefreshInterval(false, media));
}

function StudentWorkspace({ appointmentId, access }: { appointmentId: string; access: ECounselingAccess }) {
  const refreshInterval = usePagePolling(appointmentId);
  const workspace = useECounselingGetMyWorkspace(appointmentId, { query: {
    retry: false,
    refetchInterval: (query) => refreshInterval(query.state.data?.data.media),
  } });
  const data = workspace.data?.data;
  useECounselingBoundaryRefresh(appointmentId, data?.provider_readiness, workspace.refetch);

  if (!data) {
    return workspace.isPending ? <WorkspaceSkeleton /> : <WorkspaceLoadError error={workspace.error} retry={() => void workspace.refetch()} />;
  }
  return <StudentSession appointmentId={appointmentId} access={access} data={data} />;
}

function StudentSession({ appointmentId, access, data }: {
  appointmentId: string;
  access: ECounselingAccess;
  data: StudentWorkspaceResponse;
}) {
  const view = useSessionCallView({ appointmentId, participantName: data.counselor.display_name });
  const routine = data.routine_interview;
  return (
    <GuidanceContextualMessages appointmentId={appointmentId} counterpartName={data.counselor.display_name} enabled>
    <div className="@container">
      <SessionHeader
        appointmentId={appointmentId}
        participant={data.counselor.display_name}
        appointment={data.appointment}
        mediaPolicyVersion={data.media.media_policy_version}
      />
      {/* The video gets the larger column; a Student's work is the permission decisions. */}
      <div className="grid items-start gap-4 @4xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] @4xl:gap-5">
        <CallStage
          className={cn(phoneBleed, sessionStageClass.balanced, "[--call-stage-max-height:max(14rem,calc(100dvh-18rem))]")}
          call={view.call}
          participantName={data.counselor.display_name}
          readiness={data.provider_readiness}
          canJoin={access.canJoinSelf}
          media={data.media}
          onJoin={view.join}
          onLeave={view.leave}
          joinBlocked={view.joinBlocked}
          audio={view.audio}
        />
        <div className="min-w-0 space-y-4">
          <StudentConsentPanel appointmentId={appointmentId} access={access} media={data.media} inCall={view.inCall} />
          <SessionDetails
            appointment={data.appointment}
            routine={routine ? { id: routine.id, status: `${routineIntakeStatusLabel(routine.intake_status)} Intake` } : null}
            media={data.media}
          />
        </div>
      </div>
    </div>
    </GuidanceContextualMessages>
  );
}

function CounselorWorkspace({ appointmentId, access }: { appointmentId: string; access: ECounselingAccess }) {
  const refreshInterval = usePagePolling(appointmentId);
  const workspace = useECounselingGetAssignedWorkspace(appointmentId, { query: {
    retry: false,
    refetchInterval: (query) => refreshInterval(query.state.data?.data.media),
  } });
  const data = workspace.data?.data;
  useECounselingBoundaryRefresh(appointmentId, data?.provider_readiness, workspace.refetch);

  if (!data) {
    return workspace.isPending ? <WorkspaceSkeleton /> : <WorkspaceLoadError error={workspace.error} retry={() => void workspace.refetch()} />;
  }
  return (
    <CounselorSession
      appointmentId={appointmentId}
      access={access}
      data={data}
      sessionStateCurrent={!workspace.isRefetchError}
    />
  );
}

function EncounterSection({ workspace, canManage, defaultOpen }: { workspace: CounselorWorkspaceResponse; canManage: boolean; defaultOpen: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const recorded = Boolean(workspace.counseling_encounter?.recorded);
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

  // Documenting the encounter is separate from recording audio or video, and sits apart from the
  // call controls.
  return (
    <DisclosureSection title="Counseling Encounter" status={recorded ? "Documented" : "Not documented yet"} defaultOpen={defaultOpen}>
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <p className="text-sm text-muted">{recorded ? "Encounter recorded." : "Document the encounter once the conversation has taken place."}</p>
        {recorded && workspace.counseling_encounter ? (
          <Link className={buttonVariants({ variant: "secondary" })} href={`/portal/counseling/encounters/${workspace.counseling_encounter.id}`}>View encounter</Link>
        ) : canManage ? (
          <Button variant="secondary" disabled={uncertain} onClick={() => setOpen(true)}>
            {uncertain ? "Recording result unconfirmed" : "Record encounter"}
          </Button>
        ) : null}
      </div>
      {canManage && !recorded ? <RecordEncounterDialog open={open} onOpenChange={setOpen} preset={preset} onUncertain={() => setUncertain(true)} onCreated={handleCreated} /> : null}
    </DisclosureSection>
  );
}

function StudentInformation({ appointmentId, available, defaultOpen }: { appointmentId: string; available: boolean; defaultOpen: boolean }) {
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
  const counselingAccess = getCounselingAccess(user);
  const context = useCounselingContextGetOverview(CounselingContextAnchorType.APPOINTMENT, appointmentId, {
    query: { enabled: available, retry: false },
  });
  if (!available) {
    return (
      <DisclosureSection title="Student information" status="Unavailable right now">
        <p className="px-1 text-sm text-muted">Student information isn’t available for this session right now.</p>
      </DisclosureSection>
    );
  }
  const status = context.isPending ? "Loading…" : context.isError && !context.data ? "Couldn’t load" : null;
  return (
    <DisclosureSection title="Student information" status={status} defaultOpen={defaultOpen}>
      {context.isPending ? (
        <div aria-busy="true"><span className="sr-only">Loading student information…</span><Skeleton className="h-10 w-full" /><Skeleton className="mt-3 h-40 w-full" /></div>
      ) : !context.data?.data ? (
        <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void context.refetch()}>Retry</Button>}>Student information couldn’t be loaded. Try again.</Notice>
      ) : (
        <CounselingContextPanel
          anchorType={CounselingContextAnchorType.APPOINTMENT}
          anchorId={appointmentId}
          overview={context.data.data}
          access={counselingAccess}
          showHeading={false}
          onPublished={() => void queryClient.invalidateQueries({ queryKey: getCounselingContextGetOverviewQueryKey(CounselingContextAnchorType.APPOINTMENT, appointmentId) })}
        />
      )}
    </DisclosureSection>
  );
}

function CounselorSession({ appointmentId, access, data, sessionStateCurrent }: {
  appointmentId: string;
  access: ECounselingAccess;
  data: CounselorWorkspaceResponse;
  sessionStateCurrent: boolean;
}) {
  const view = useSessionCallView({ appointmentId, participantName: data.student.display_name });
  const inCall = view.inCall;
  const { user } = usePortalSession();
  const counselingAccess = getCounselingAccess(user);
  const rootRef = useRef<HTMLDivElement>(null);
  const wide = useWideWorkspace(rootRef);
  const [preset, setPreset] = useState<LayoutPreset>("balanced");
  const media = useCounselorMedia({ appointmentId, access, workspace: data, inCall, sessionStateCurrent });
  // Secondary work starts open beside the call; in Focus and on narrow screens it starts collapsed
  // below it, each section keeping a one-line status.
  const secondaryOpen = wide && preset !== "focus";
  const routine = data.routine_interview;

  return (
    // Opening Messages narrows this workspace, so its own container queries fall back to one column;
    // the call stage stays where it is in the tree and the call runtime never notices (ADR-094).
    <GuidanceContextualMessages appointmentId={appointmentId} counterpartName={data.student.display_name} enabled>
    <div ref={rootRef} className="@container">
      <SessionHeader
        appointmentId={appointmentId}
        participant={data.student.display_name}
        appointment={data.appointment}
        mediaPolicyVersion={data.media.media_policy_version}
        layoutControl={wide ? <LayoutPresetControl value={preset} onChange={setPreset} /> : undefined}
      />
      <div data-layout={preset} className={cn("grid items-start gap-4 @4xl:gap-5", sessionGrid[preset])}>
        <CallStage
          className={cn(phoneBleed, sessionStageClass[preset], "[--call-stage-max-height:max(14rem,calc(100dvh-18rem))]")}
          call={view.call}
          participantName={data.student.display_name}
          readiness={data.provider_readiness}
          canJoin={access.canJoinAssigned}
          media={data.media}
          governedControls={<GovernedCaptureControls media={media} />}
          devicesInTray="when-wide"
          onJoin={view.join}
          onLeave={view.leave}
          joinBlocked={view.joinBlocked}
          audio={view.audio}
          footer={<CounselorMediaStrip media={media} />}
        />
        <div className="min-w-0 space-y-2">
          <StudentInformation appointmentId={appointmentId} available={data.counseling_context_available} defaultOpen={secondaryOpen} />
          <EncounterSection workspace={data} canManage={counselingAccess.canManageAssigned} defaultOpen={secondaryOpen} />
          <SessionFiles appointmentId={appointmentId} media={data.media} canAccess={access.canAccessMediaAssigned} defaultOpen={secondaryOpen} />
          <SessionDetails
            appointment={data.appointment}
            routine={routine ? { id: routine.id, status: `${routineIntakeStatusLabel(routine.intake_status)} Intake · ${routineEvaluationStatusLabel(routine.evaluation_status)} Evaluation` } : null}
          />
        </div>
      </div>
      <CaptureStartDialogs media={media} />
    </div>
    </GuidanceContextualMessages>
  );
}
