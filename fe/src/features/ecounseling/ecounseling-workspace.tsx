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
import { unconfirmedEncounterMessage } from "@/features/counseling/counseling-shared";
import { RecordEncounterDialog } from "@/features/counseling/record-encounter-dialog";
import { CallStage } from "@/features/ecounseling/call/call-stage";
import { useSessionCallView } from "@/features/ecounseling/runtime/use-session-call-view";
import { CaptureStartDialogs, CounselorMediaStrip, GovernedCaptureControls, useCounselorMedia } from "@/features/ecounseling/counselor-media";
import { getECounselingAccess, type ECounselingAccess } from "@/features/ecounseling/ecounseling-access";
import { captureStatusLabel, ecounselingErrorMessage, sessionEncounterPreset } from "@/features/ecounseling/ecounseling-shared";
import { ECounselingHelp } from "@/features/ecounseling/session-help";
import { SessionFiles } from "@/features/ecounseling/session-files";
import { LayoutPresetControl, phoneBleed, sessionGrid, sessionStageClass, useWideWorkspace, type LayoutPreset } from "@/features/ecounseling/session-layout";
import { StudentConsentPanel } from "@/features/ecounseling/student-consent-panel";
import { useECounselingResourceDenial } from "@/features/ecounseling/use-ecounseling-resource-access";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { canShowLastKnownData, safeQueryData } from "@/features/freshness/query-freshness";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { PersonAvatar } from "@/features/account/components/person-avatar";
import { accountDisplayName } from "@/features/account/components/account-avatar";
import { GuidanceContextualMessages, GuidanceMessagesTrigger } from "@/features/guidance-messages/guidance-contextual-messages";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { routineEvaluationStatusLabel, routineIntakeStatusLabel } from "@/features/routine-interviews/routine-interviews-shared";
import type { AppointmentWorkspaceSummary, CounselorWorkspaceResponse, MediaWorkspaceState, ProviderReadiness, StudentWorkspaceResponse } from "@/lib/api/generated/model";
import { CounselingContextAnchorType, ECounselingCaptureStatus, ECounselingJoinState } from "@/lib/api/generated/model";
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
import { useProfileGetMyProfile } from "@/lib/api/generated/profile/profile";
import { cn } from "@/lib/utils/cn";


// Who the session is with, its status and time. The Appointment reference and the Routine Interview
// sit under Session details, lower on the page.
function SessionHeader({
  appointmentId,
  participant,
  participantPhotoUrl,
  participantPhotoUpdatedAt,
  selfName,
  selfPhotoUrl,
  selfPhotoUpdatedAt,
  appointment,
  mediaPolicyVersion,
  layoutControl,
}: {
  appointmentId: string;
  participant: string;
  participantPhotoUrl?: string | null;
  participantPhotoUpdatedAt?: string | null;
  selfName: string;
  selfPhotoUrl?: string | null;
  selfPhotoUpdatedAt?: string | null;
  appointment: AppointmentWorkspaceSummary;
  mediaPolicyVersion: MediaWorkspaceState["media_policy_version"];
  // Shown beside the title only where the workspace is wide enough for presets to change anything.
  layoutControl?: ReactNode;
}) {
  return (
    <PageHeader
      title={<span className="inline-flex items-center gap-3"><PersonAvatar displayName={participant} photoUrl={participantPhotoUrl} photoUpdatedAt={participantPhotoUpdatedAt} size="standard" />{participant}</span>}
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
      <p className="mt-2 inline-flex items-center gap-2 text-sm text-muted"><PersonAvatar displayName={selfName} photoUrl={selfPhotoUrl} photoUpdatedAt={selfPhotoUpdatedAt} size="compact" />You · {selfName}</p>
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
        ["Recording", media.recording.capture_status, media.recording.artifact_disposed_at, "recording"],
        ["Transcription", media.transcription.capture_status, media.transcription.artifact_disposed_at, "transcription"],
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
        {captured.map(([label, status, disposedAt, kind]) => (
          <div key={label} className="contents">
            <dt className="text-muted">{label}</dt>
            <dd className="text-ink">{disposedAt ? "Deleted under an approved retention rule" : captureStatusLabel(status, kind)}</dd>
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

// The portal freshness coordinator owns the one workspace safety poll per appointment.
// Page and persistent-call observers continue sharing the same canonical query.
function StudentWorkspace({ appointmentId, access }: { appointmentId: string; access: ECounselingAccess }) {
  const denial = useECounselingResourceDenial(appointmentId);
  const workspace = useECounselingGetMyWorkspace(appointmentId, { query: {
    retry: false,
    enabled: !denial,
    refetchInterval: false,
  } });
  const data = denial ? undefined : safeQueryData(workspace)?.data;
  useECounselingBoundaryRefresh(appointmentId, data?.provider_readiness, workspace.refetch);

  if (!data) {
    return !denial && workspace.isPending ? <WorkspaceSkeleton /> : <WorkspaceLoadError error={denial?.error ?? workspace.error} retry={() => void workspace.refetch()} />;
  }
  return (
    <>
      {canShowLastKnownData(workspace) ? <RefreshFailureNotice onRetry={() => void workspace.refetch()} retrying={workspace.isFetching} /> : null}
      <StudentSession appointmentId={appointmentId} access={access} data={data} />
    </>
  );
}

function StudentSession({ appointmentId, access, data }: {
  appointmentId: string;
  access: ECounselingAccess;
  data: StudentWorkspaceResponse;
}) {
  const { user } = usePortalSession();
  const profile = useProfileGetMyProfile({ query: { retry: false, staleTime: 60_000 } }).data?.data;
  const selfName = accountDisplayName(user, profile);
  const view = useSessionCallView({
    appointmentId,
    participantName: data.counselor.display_name,
    endsAt: data.appointment.ends_at,
  });
  const routine = data.routine_interview;
  return (
    <GuidanceContextualMessages appointmentId={appointmentId} counterpartName={data.counselor.display_name} enabled>
    <div className="@container">
      <SessionHeader
        appointmentId={appointmentId}
        participant={data.counselor.display_name}
        participantPhotoUrl={data.counselor.profile_photo_url}
        participantPhotoUpdatedAt={data.counselor.profile_photo_updated_at}
        selfName={selfName}
        selfPhotoUrl={profile?.profile_photo_url}
        selfPhotoUpdatedAt={profile?.profile_photo_updated_at}
        appointment={data.appointment}
        mediaPolicyVersion={data.media.media_policy_version}
      />
      {/* The video gets the larger column; a Student's work is the permission decisions. */}
      <div className="grid items-start gap-4 @4xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] @4xl:gap-5">
        <CallStage
          className={cn(phoneBleed, sessionStageClass.balanced, "[--call-stage-max-height:max(14rem,calc(100dvh-18rem))]")}
          call={view.call}
          participantName={data.counselor.display_name}
          participantPhotoUrl={data.counselor.profile_photo_url}
          participantPhotoUpdatedAt={data.counselor.profile_photo_updated_at}
          selfName={selfName}
          selfPhotoUrl={profile?.profile_photo_url}
          selfPhotoUpdatedAt={profile?.profile_photo_updated_at}
          readiness={data.provider_readiness}
          canJoin={access.canJoinSelf}
          media={data.media}
          timing={view.timing}
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
  const denial = useECounselingResourceDenial(appointmentId);
  const workspace = useECounselingGetAssignedWorkspace(appointmentId, { query: {
    retry: false,
    enabled: !denial,
    refetchInterval: false,
  } });
  const data = denial ? undefined : safeQueryData(workspace)?.data;
  useECounselingBoundaryRefresh(appointmentId, data?.provider_readiness, workspace.refetch);

  if (!data) {
    return !denial && workspace.isPending ? <WorkspaceSkeleton /> : <WorkspaceLoadError error={denial?.error ?? workspace.error} retry={() => void workspace.refetch()} />;
  }
  return (
    <>
      {canShowLastKnownData(workspace) ? <RefreshFailureNotice onRetry={() => void workspace.refetch()} retrying={workspace.isFetching} /> : null}
      <CounselorSession
        appointmentId={appointmentId}
        access={access}
        data={data}
        sessionStateCurrent={!workspace.isRefetchError && !workspace.isFetching}
      />
    </>
  );
}

function EncounterSection({ workspace, canManage, defaultOpen }: { workspace: CounselorWorkspaceResponse; canManage: boolean; defaultOpen: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [checking, setChecking] = useState(false);
  const [alreadyRecorded, setAlreadyRecorded] = useState(false);
  const actionsRef = useRef<HTMLDivElement>(null);
  const encounter = workspace.counseling_encounter;
  const recorded = Boolean(encounter?.recorded);
  const preset = sessionEncounterPreset(workspace);

  // Reloads what this session shows about its Encounter and the lists that include it.
  async function reloadEncounter() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getECounselingGetAssignedWorkspaceQueryKey(workspace.appointment.id) }),
      queryClient.invalidateQueries({ queryKey: getCounselingListMyEncountersQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getCounselingContextGetOverviewQueryKey(CounselingContextAnchorType.APPOINTMENT, workspace.appointment.id) }),
      ...(workspace.routine_interview ? [queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListEncounterCandidatesQueryKey(workspace.routine_interview.id) })] : []),
    ]);
  }

  async function handleCreated() {
    await reloadEncounter();
    setOpen(false);
  }

  async function handleAlreadyRecorded() {
    await reloadEncounter();
    setAlreadyRecorded(true);
    setOpen(false);
  }

  // An unconfirmed save is checked, never retried here: the reload shows the Encounter if it was
  // recorded, and otherwise the result stays unconfirmed.
  async function checkAgain() {
    setChecking(true);
    try {
      await reloadEncounter();
    } finally {
      setChecking(false);
    }
  }

  // The backend can report an Encounter this workspace does not list, e.g. one recorded before a
  // reassignment; it is still recorded.
  const status = recorded || alreadyRecorded ? "Recorded" : uncertain ? "Not confirmed" : "Not yet recorded";
  const message = alreadyRecorded
    ? `An encounter was already recorded for this Appointment.${recorded ? " The latest details are now shown." : ""}`
    : recorded ? "Encounter recorded." : uncertain ? unconfirmedEncounterMessage : "Record the encounter after the counseling conversation.";

  // Documenting the encounter is separate from recording audio or video, and sits apart from the
  // call controls.
  return (
    <DisclosureSection title="Counseling Encounter" status={status} defaultOpen={defaultOpen}>
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <p aria-live="polite" className="min-w-0 text-sm text-muted">{message}</p>
        <div ref={actionsRef} className="flex flex-wrap gap-2">
          {recorded && encounter ? (
            <Link className={buttonVariants({ variant: "secondary" })} href={`/portal/counseling/encounters/${encounter.id}`}>View encounter</Link>
          ) : alreadyRecorded ? (
            <Link className={buttonVariants({ variant: "secondary" })} href="/portal/counseling#encounters">View encounters</Link>
          ) : canManage && uncertain ? (
            <>
              <Button variant="secondary" aria-busy={checking} onClick={() => void checkAgain()}>{checking ? "Checking…" : "Check again"}</Button>
              <Link className={buttonVariants({ variant: "quiet" })} href="/portal/counseling#encounters">View encounters</Link>
            </>
          ) : canManage ? (
            <Button variant="secondary" onClick={() => setOpen(true)}>Record encounter</Button>
          ) : null}
        </div>
      </div>
      {canManage ? (
        <RecordEncounterDialog
          open={open && !recorded && !alreadyRecorded}
          onOpenChange={setOpen}
          preset={preset}
          onUncertain={() => setUncertain(true)}
          onCreated={handleCreated}
          onAlreadyRecorded={handleAlreadyRecorded}
          // Recording replaces the opener with View encounter, so focus moves to this section's action.
          onCloseAutoFocus={(event) => {
            const action = actionsRef.current?.querySelector<HTMLElement>("a, button");
            if (!action) return;
            event.preventDefault();
            action.focus();
          }}
        />
      ) : null}
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
  const data = safeQueryData(context)?.data;
  if (!available) {
    return (
      <DisclosureSection title="Student information" status="Unavailable right now">
        <p className="px-1 text-sm text-muted">Student information isn’t available for this session right now.</p>
      </DisclosureSection>
    );
  }
  const status = context.isPending ? "Loading…" : context.isError && !data ? "Couldn’t load" : null;
  return (
    <DisclosureSection title="Student information" status={status} defaultOpen={defaultOpen}>
      {context.isPending ? (
        <div aria-busy="true"><span className="sr-only">Loading student information…</span><Skeleton className="h-10 w-full" /><Skeleton className="mt-3 h-40 w-full" /></div>
      ) : !data ? (
        <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void context.refetch()}>Retry</Button>}>Student information couldn’t be loaded. Try again.</Notice>
      ) : (
        <>
          {canShowLastKnownData(context) ? <RefreshFailureNotice onRetry={() => void context.refetch()} retrying={context.isFetching} /> : null}
          <CounselingContextPanel
            anchorType={CounselingContextAnchorType.APPOINTMENT}
            anchorId={appointmentId}
            overview={data}
            access={counselingAccess}
            showHeading={false}
            onPublished={() => void queryClient.invalidateQueries({ queryKey: getCounselingContextGetOverviewQueryKey(CounselingContextAnchorType.APPOINTMENT, appointmentId) })}
          />
        </>
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
  const view = useSessionCallView({
    appointmentId,
    participantName: data.student.display_name,
    endsAt: data.appointment.ends_at,
  });
  const inCall = view.inCall;
  const { user } = usePortalSession();
  const profile = useProfileGetMyProfile({ query: { retry: false, staleTime: 60_000 } }).data?.data;
  const selfName = accountDisplayName(user, profile);
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
        participantPhotoUrl={data.student.profile_photo_url}
        participantPhotoUpdatedAt={data.student.profile_photo_updated_at}
        selfName={selfName}
        selfPhotoUrl={profile?.profile_photo_url}
        selfPhotoUpdatedAt={profile?.profile_photo_updated_at}
        appointment={data.appointment}
        mediaPolicyVersion={data.media.media_policy_version}
        layoutControl={wide ? <LayoutPresetControl value={preset} onChange={setPreset} /> : undefined}
      />
      <div data-layout={preset} className={cn("grid items-start gap-4 @4xl:gap-5", sessionGrid[preset])}>
        <CallStage
          className={cn(phoneBleed, sessionStageClass[preset], "[--call-stage-max-height:max(14rem,calc(100dvh-18rem))]")}
          call={view.call}
          participantName={data.student.display_name}
          participantPhotoUrl={data.student.profile_photo_url}
          participantPhotoUpdatedAt={data.student.profile_photo_updated_at}
          selfName={selfName}
          selfPhotoUrl={profile?.profile_photo_url}
          selfPhotoUpdatedAt={profile?.profile_photo_updated_at}
          readiness={data.provider_readiness}
          canJoin={access.canJoinAssigned}
          media={data.media}
          timing={view.timing}
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
