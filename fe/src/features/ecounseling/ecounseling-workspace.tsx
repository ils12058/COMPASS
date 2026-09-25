"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { CounselingContextPanel } from "@/features/counseling/counseling-workspace";
import { RecordEncounterForm, type EncounterOriginPreset } from "@/features/counseling/record-encounter-form";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { CounselorMediaControls } from "@/features/ecounseling/counselor-media-controls";
import { DailySessionFrame } from "@/features/ecounseling/daily-session-frame";
import { getECounselingAccess } from "@/features/ecounseling/ecounseling-access";
import { ecounselingErrorMessage, formatECounselingDateTime, hasLiveOrTransitionalMedia } from "@/features/ecounseling/ecounseling-shared";
import { StudentConsentPanel } from "@/features/ecounseling/student-consent-panel";
import { usePortalSession } from "@/features/portal/components/portal-session";
import type { CounselorWorkspaceResponse, JoinCredentialResponse } from "@/lib/api/generated/model";
import { CounselingContextAnchorType, CounselingEntryMode, DeliveryMode } from "@/lib/api/generated/model";
import {
  getCounselingContextGetOverviewQueryKey,
  getCounselingListMyEncountersQueryKey,
  useCounselingContextGetOverview,
} from "@/lib/api/generated/counseling/counseling";
import { getRoutineInterviewsListEncounterCandidatesQueryKey } from "@/lib/api/generated/routine-interviews/routine-interviews";
import {
  getECounselingGetAssignedWorkspaceQueryKey,
  useECounselingCreateJoinCredential,
  useECounselingGetAssignedWorkspace,
  useECounselingGetMyWorkspace,
} from "@/lib/api/generated/e-counseling/e-counseling";

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
    return <section aria-labelledby="e-counseling-encounter-heading" className="border-t border-border pt-5"><h2 id="e-counseling-encounter-heading" className="font-heading text-lg font-semibold text-ink">Counseling Encounter</h2><p className="mt-2 text-sm text-ink">Encounter recorded.</p><Link className="mt-3 inline-flex min-h-10 items-center rounded-md border border-border px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" href={`/portal/counseling/encounters/${workspace.counseling_encounter.id}`}>View encounter</Link></section>;
  }

  return <section aria-labelledby="e-counseling-encounter-heading" className="border-t border-border pt-5"><h2 id="e-counseling-encounter-heading" className="font-heading text-lg font-semibold text-ink">Counseling Encounter</h2><p className="mt-2 text-sm text-muted">No Encounter has been recorded for this session yet. Recording an Encounter is separate from media consent and capture.</p>{canManage ? open ? <div className="mt-4 border-y border-border py-5"><RecordEncounterForm preset={preset} onCancel={() => setOpen(false)} onUncertain={() => setUncertain(true)} onCreated={() => void handleCreated()} /></div> : <Button className="mt-3" disabled={uncertain} onClick={() => setOpen(true)}>{uncertain ? "Recording result unconfirmed" : "Record completed encounter"}</Button> : null}</section>;
}

function SessionPageHeader({ title, description }: { title: string; description: string }) {
  return <header className="mb-6 border-b border-border pb-5"><h1 className="font-heading text-3xl font-bold text-ink">{title}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{description}</p></header>;
}

function WorkspaceLoadError({ error, retry }: { error: unknown; retry: () => void }) {
  return <section role="alert" className="max-w-2xl border-y border-border py-7"><h1 className="font-heading text-2xl font-semibold text-ink">E-Counseling unavailable</h1><p className="mt-3 text-sm leading-6 text-muted">{ecounselingErrorMessage(error, "This E-Counseling session is not currently available.")}</p><Button className="mt-4" variant="secondary" onClick={retry}>Retry</Button><Link className="ml-2 inline-flex min-h-10 items-center rounded-md px-4 py-2 text-sm font-semibold text-brand underline" href="/portal/appointments/my">Return to appointments</Link></section>;
}

export function ECounselingWorkspace({ appointmentId }: { appointmentId: string }) {
  const { user } = usePortalSession();
  const access = getECounselingAccess(user);
  if (!access.hasWorkspace) {
    return <section role="status" className="max-w-2xl border-y border-border py-7"><h1 className="font-heading text-2xl font-semibold text-ink">E-Counseling unavailable</h1><p className="mt-3 text-sm leading-6 text-muted">This session is not available within your current access.</p></section>;
  }
  return access.isStudent
    ? <StudentWorkspace appointmentId={appointmentId} access={access} />
    : <CounselorWorkspace appointmentId={appointmentId} access={access} />;
}

function StudentWorkspace({ appointmentId, access }: { appointmentId: string; access: ReturnType<typeof getECounselingAccess> }) {
  const [credential, setCredential] = useState<JoinCredentialResponse | null>(null);
  const [showDailyFrame, setShowDailyFrame] = useState(false);
  const [frameGeneration, setFrameGeneration] = useState(0);
  const [localCallJoined, setLocalCallJoined] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);
  const workspace = useECounselingGetMyWorkspace(appointmentId, { query: {
    retry: false,
    refetchInterval: (query) => localCallJoined || hasLiveOrTransitionalMedia(query.state.data?.data.media) ? 7000 : false,
  } });
  const joinCredential = useECounselingCreateJoinCredential({ mutation: { retry: false } });
  const joinMutationRef = useRef(joinCredential);
  const data = workspace.data?.data;
  const media = data?.media;

  useEffect(() => { joinMutationRef.current = joinCredential; }, [joinCredential]);
  useEffect(() => () => joinMutationRef.current.reset(), []);

  async function requestJoin() {
    setJoinError(null);
    try {
      const result = await joinCredential.mutateAsync({ appointmentId });
      setCredential(result.data);
      setFrameGeneration((generation) => generation + 1);
      setShowDailyFrame(true);
    } catch (error) {
      joinCredential.reset();
      setJoinError(ecounselingErrorMessage(error, "A secure session could not be opened. Refresh the session state and try again."));
      void workspace.refetch();
    }
  }

  if (workspace.isPending) return <div aria-busy="true"><span className="sr-only">Loading E-Counseling session…</span><Skeleton className="h-10 w-2/3" /><Skeleton className="mt-5 h-80 w-full" /><Skeleton className="mt-4 h-24 w-full" /></div>;
  if (workspace.isError || !data || !media) return <WorkspaceLoadError error={workspace.error} retry={() => void workspace.refetch()} />;

  const joinAvailable = access.canJoinSelf && data.provider_readiness.daily_enabled && data.provider_readiness.join_allowed;

  return (
    <div className="mx-auto max-w-screen-2xl">
      <SessionPageHeader title="E-Counseling session" description="Your online Counseling Appointment and session-safe information. Media consent is optional and does not affect your access to Counseling." />
      <div className="grid gap-7 xl:grid-cols-[minmax(0,1.8fr)_minmax(19rem,0.8fr)]">
        <div className="min-w-0 space-y-6">
          {showDailyFrame ? <DailySessionFrame key={frameGeneration} credential={credential} onJoined={() => { setCredential(null); joinCredential.reset(); setLocalCallJoined(true); }} onLeft={() => { setLocalCallJoined(false); setShowDailyFrame(false); setCredential(null); joinCredential.reset(); }} onFailed={() => { setJoinError("The video session could not be opened. Request a fresh join to try again."); setLocalCallJoined(false); setShowDailyFrame(false); setCredential(null); joinCredential.reset(); void workspace.refetch(); }} /> : <section aria-label="Session video" className="flex aspect-video min-h-60 flex-col items-center justify-center border border-border bg-surface-muted px-5 text-center"><h2 className="font-heading text-xl font-semibold text-ink">Session ready</h2><p className="mt-2 max-w-md text-sm leading-6 text-muted">Joining creates or opens the provider session. No room is provisioned just by visiting this page.</p><Button className="mt-4" disabled={!joinAvailable || joinCredential.isPending || showDailyFrame || localCallJoined} onClick={() => void requestJoin()}>{joinCredential.isPending ? "Preparing secure session…" : "Join session"}</Button></section>}
          {joinError ? <p role="alert" className="text-sm text-danger">{joinError}</p> : null}
          {!data.provider_readiness.daily_enabled ? <p role="status" className="border-y border-border py-4 text-sm text-muted">The video provider is not currently enabled. Counseling remains available.</p> : null}
          {data.provider_readiness.daily_enabled && !data.provider_readiness.join_allowed ? <p role="status" className="border-y border-border py-4 text-sm text-muted">Joining is not currently available for this session.</p> : null}
        </div>
        <aside className="min-w-0 space-y-6">
          <section aria-labelledby="student-session-details-heading" className="border-y border-border py-5">
            <h2 id="student-session-details-heading" className="font-heading text-xl font-semibold text-ink">My session</h2>
            <dl className="mt-3 divide-y divide-border">
              <div className="py-3"><dt className="text-xs font-semibold text-muted">Appointment</dt><dd className="mt-1 break-all font-mono text-sm text-ink">{data.appointment.reference_code}</dd><dd className="mt-1 text-xs text-muted">{data.appointment.status.toLowerCase().replaceAll("_", " ")} · {data.appointment.delivery_mode.toLowerCase().replaceAll("_", " ")}</dd></div>
              <div className="py-3"><dt className="text-xs font-semibold text-muted">Date and time</dt><dd className="mt-1 text-sm text-ink">{formatECounselingDateTime(data.appointment.starts_at)} – {formatECounselingDateTime(data.appointment.ends_at)}</dd></div>
              <div className="py-3"><dt className="text-xs font-semibold text-muted">Counselor</dt><dd className="mt-1 text-sm text-ink">{data.counselor.display_name}</dd></div>
              <div className="py-3"><dt className="text-xs font-semibold text-muted">Routine Interview</dt><dd className="mt-1 text-sm text-ink">{data.routine_interview ? `Intake · ${data.routine_interview.intake_status.toLowerCase().replaceAll("_", " ")}` : "No linked Routine Interview"}</dd>{data.routine_interview ? <dd className="mt-2"><Link className="text-sm font-semibold text-brand underline" href={`/portal/routine-interviews/${data.routine_interview.id}`}>Open Routine Interview</Link></dd> : null}</div>
              <div className="py-3"><dt className="text-xs font-semibold text-muted">Provider readiness</dt><dd className="mt-1 text-sm text-ink">{data.provider_readiness.daily_enabled ? data.provider_readiness.room_provisioned ? "Room ready" : "Room will be provisioned when a participant joins" : "Video provider unavailable"}</dd></div>
            </dl>
          </section>
          <StudentConsentPanel appointmentId={appointmentId} access={access} media={media} />
        </aside>
      </div>
    </div>
  );
}

function CounselorWorkspace({ appointmentId, access }: { appointmentId: string; access: ReturnType<typeof getECounselingAccess> }) {
  const { user } = usePortalSession();
  const counselingAccess = getCounselingAccess(user);
  const [credential, setCredential] = useState<JoinCredentialResponse | null>(null);
  const [showDailyFrame, setShowDailyFrame] = useState(false);
  const [frameGeneration, setFrameGeneration] = useState(0);
  const [localCallJoined, setLocalCallJoined] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const workspace = useECounselingGetAssignedWorkspace(appointmentId, { query: {
    retry: false,
    refetchInterval: (query) => localCallJoined || hasLiveOrTransitionalMedia(query.state.data?.data.media) ? 7000 : false,
  } });
  const joinCredential = useECounselingCreateJoinCredential({ mutation: { retry: false } });
  const joinMutationRef = useRef(joinCredential);
  const data = workspace.data?.data;
  const media = data?.media;
  const context = useCounselingContextGetOverview(CounselingContextAnchorType.APPOINTMENT, appointmentId, {
    query: { enabled: Boolean(data), retry: false },
  });

  useEffect(() => { joinMutationRef.current = joinCredential; }, [joinCredential]);
  useEffect(() => () => joinMutationRef.current.reset(), []);

  async function requestJoin() {
    setJoinError(null);
    try {
      const result = await joinCredential.mutateAsync({ appointmentId });
      setCredential(result.data);
      setFrameGeneration((generation) => generation + 1);
      setShowDailyFrame(true);
    } catch (error) {
      joinCredential.reset();
      setJoinError(ecounselingErrorMessage(error, "A secure session could not be opened. Refresh the session state and try again."));
      void workspace.refetch();
    }
  }

  if (workspace.isPending) return <div aria-busy="true"><span className="sr-only">Loading E-Counseling session…</span><Skeleton className="h-10 w-2/3" /><Skeleton className="mt-5 h-80 w-full" /><Skeleton className="mt-4 h-24 w-full" /></div>;
  if (workspace.isError || !data || !media) return <WorkspaceLoadError error={workspace.error} retry={() => void workspace.refetch()} />;

  const joinAvailable = access.canJoinAssigned && data.provider_readiness.daily_enabled && data.provider_readiness.join_allowed;

  return (
    <div className="mx-auto max-w-screen-2xl">
      <SessionPageHeader title="E-Counseling session" description="Assigned online Counseling Appointment, provider status, and the Student’s scoped Counseling context." />
      <div className="grid gap-7 xl:grid-cols-[minmax(0,1.8fr)_minmax(19rem,0.8fr)]">
        <div className="min-w-0 space-y-6">
          {showDailyFrame ? <DailySessionFrame key={frameGeneration} credential={credential} onJoined={() => { setCredential(null); joinCredential.reset(); setLocalCallJoined(true); }} onLeft={() => { setLocalCallJoined(false); setShowDailyFrame(false); setCredential(null); joinCredential.reset(); }} onFailed={() => { setJoinError("The video session could not be opened. Request a fresh join to try again."); setLocalCallJoined(false); setShowDailyFrame(false); setCredential(null); joinCredential.reset(); void workspace.refetch(); }} /> : <section aria-label="Session video" className="flex aspect-video min-h-60 flex-col items-center justify-center border border-border bg-surface-muted px-5 text-center"><h2 className="font-heading text-xl font-semibold text-ink">Session ready</h2><p className="mt-2 max-w-md text-sm leading-6 text-muted">Joining creates or opens the provider session. No room is provisioned just by visiting this page.</p><Button className="mt-4" disabled={!joinAvailable || joinCredential.isPending || showDailyFrame || localCallJoined} onClick={() => void requestJoin()}>{joinCredential.isPending ? "Preparing secure session…" : "Join session"}</Button></section>}
          {joinError ? <p role="alert" className="text-sm text-danger">{joinError}</p> : null}
          {!data.provider_readiness.daily_enabled ? <p role="status" className="border-y border-border py-4 text-sm text-muted">The video provider is not currently enabled. Counseling remains available.</p> : null}
          {data.provider_readiness.daily_enabled && !data.provider_readiness.join_allowed ? <p role="status" className="border-y border-border py-4 text-sm text-muted">Joining is not currently available for this session.</p> : null}
          <section aria-labelledby="counselor-session-details-heading" className="border-y border-border py-5">
            <h2 id="counselor-session-details-heading" className="font-heading text-lg font-semibold text-ink">Session details</h2>
            <dl className="mt-3 grid gap-4 sm:grid-cols-2"><div><dt className="text-xs font-semibold text-muted">Appointment</dt><dd className="mt-1 break-all font-mono text-sm text-ink">{data.appointment.reference_code}</dd></div><div><dt className="text-xs font-semibold text-muted">Date and time</dt><dd className="mt-1 text-sm text-ink">{formatECounselingDateTime(data.appointment.starts_at)} – {formatECounselingDateTime(data.appointment.ends_at)}</dd></div><div><dt className="text-xs font-semibold text-muted">Student</dt><dd className="mt-1 text-sm text-ink">{data.student.display_name}</dd></div><div><dt className="text-xs font-semibold text-muted">Routine Interview</dt><dd className="mt-1 text-sm text-ink">{data.routine_interview ? `Intake · ${data.routine_interview.intake_status.toLowerCase().replaceAll("_", " ")} · Evaluation · ${data.routine_interview.evaluation_status.toLowerCase().replaceAll("_", " ")}` : "No linked Routine Interview"}</dd>{data.routine_interview ? <dd className="mt-2"><Link className="text-sm font-semibold text-brand underline" href={`/portal/routine-interviews/${data.routine_interview.id}`}>Open Routine Interview</Link></dd> : null}</div><div><dt className="text-xs font-semibold text-muted">Provider readiness</dt><dd className="mt-1 text-sm text-ink">{data.provider_readiness.daily_enabled ? data.provider_readiness.room_provisioned ? "Room ready" : "Room will be provisioned when a participant joins" : "Video provider unavailable"}</dd></div></dl>
          </section>
          <CounselorMediaControls appointmentId={appointmentId} access={access} workspace={data} />
          <RecordStatus workspace={data} canManage={counselingAccess.canManageAssigned} />
        </div>
        <aside className="min-w-0 border-t border-border pt-5 xl:border-t-0 xl:pt-0">
          {context.isPending ? <section aria-busy="true" aria-label="Loading Counseling context"><h2 className="font-heading text-xl font-semibold text-ink">Student context</h2><Skeleton className="mt-4 h-12 w-full" /><Skeleton className="mt-3 h-48 w-full" /></section> : context.isError || !context.data?.data ? <section role="status" className="border-y border-border py-5"><h2 className="font-heading text-xl font-semibold text-ink">Student context</h2><p className="mt-3 text-sm leading-6 text-muted">Counseling context is not currently available.</p><Button className="mt-3" variant="secondary" onClick={() => void context.refetch()}>Retry context</Button></section> : <CounselingContextPanel anchorType={CounselingContextAnchorType.APPOINTMENT} anchorId={appointmentId} overview={context.data.data} access={counselingAccess} onPublished={() => void queryClient.invalidateQueries({ queryKey: getCounselingContextGetOverviewQueryKey(CounselingContextAnchorType.APPOINTMENT, appointmentId) })} />}
        </aside>
      </div>
      <p className="mt-6 text-xs text-muted">Recording and transcription state is provider-backed. No transcript text, playback, or download is available here.</p>
    </div>
  );
}
