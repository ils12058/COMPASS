"use client";

import { Check, Circle, Clock, LoaderCircle, ScrollText, Square, X, type LucideIcon } from "lucide-react";
import { useId, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Disclosure } from "@/components/ui/disclosure";
import { Skeleton } from "@/components/ui/skeleton";
import { CallControl, type CallControlTone } from "@/features/ecounseling/call/call-control";
import { leaveFullscreen } from "@/features/ecounseling/call/use-fullscreen";
import type { ECounselingAccess } from "@/features/ecounseling/ecounseling-access";
import {
  captureStatusLabel,
  ecounselingErrorMessage,
  formatECounselingDateTime,
  isLiveOrTransitionalCapture,
} from "@/features/ecounseling/ecounseling-shared";
import {
  getECounselingGetAssignedWorkspaceQueryKey,
  getECounselingListAssignedConsentsQueryKey,
  useECounselingListAssignedConsents,
  useECounselingRequestConsent,
  useECounselingStartAssignedRecording,
  useECounselingStartAssignedTranscription,
  useECounselingStopAssignedRecording,
  useECounselingStopAssignedTranscription,
} from "@/lib/api/generated/e-counseling/e-counseling";
import {
  ECounselingCaptureStatus,
  ECounselingConsentDecision,
  ECounselingConsentScope,
  type ConsentResponse,
  type CounselorWorkspaceResponse,
  type ECounselingConsentStatus,
} from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";

type CaptureKind = "recording" | "transcription";

function latestConsent(rows: ConsentResponse[], scope: ECounselingConsentScope): ConsentResponse | undefined {
  return rows.filter((item) => item.scope === scope).sort((a, b) => b.requested_at.localeCompare(a.requested_at))[0];
}

function isEffectivelyApproved(row: ConsentResponse | undefined): boolean {
  return Boolean(row?.effective && row.decision === ECounselingConsentDecision.APPROVED && !row.withdrawn_at);
}

// Pending, or approved and still in effect: a request that can still lead to capture.
function isViable(row: ConsentResponse | undefined): boolean {
  return Boolean(row && !row.withdrawn_at && (row.decision === ECounselingConsentDecision.PENDING || isEffectivelyApproved(row)));
}

type PermissionState = "not-requested" | "pending" | "approved" | "invalid" | "declined" | "withdrawn";

function permissionState(row: ConsentResponse | undefined): PermissionState {
  if (!row) return "not-requested";
  if (row.withdrawn_at) return "withdrawn";
  if (row.decision === ECounselingConsentDecision.DENIED) return "declined";
  if (row.decision === ECounselingConsentDecision.PENDING) return "pending";
  return row.effective ? "approved" : "invalid";
}

const projectedStates: Record<ECounselingConsentStatus, PermissionState> = {
  NOT_REQUESTED: "not-requested",
  PENDING: "pending",
  APPROVED: "approved",
  DENIED: "declined",
  WITHDRAWN: "withdrawn",
};

const permissionCopy: Record<PermissionState, { text: (subject: string) => string; icon: LucideIcon; tone: string }> = {
  "not-requested": { text: (subject) => `${subject} not requested`, icon: Circle, tone: "text-muted" },
  pending: { text: (subject) => `${subject} · Waiting for Student`, icon: Clock, tone: "text-ink" },
  approved: { text: (subject) => `${subject} approved`, icon: Check, tone: "text-success" },
  invalid: { text: (subject) => `${subject} no longer valid`, icon: X, tone: "text-muted" },
  declined: { text: (subject) => `${subject} declined`, icon: X, tone: "text-muted" },
  withdrawn: { text: (subject) => `${subject} withdrawn`, icon: X, tone: "text-muted" },
};

type PermissionRow = {
  key: string;
  subject: string;
  state: PermissionState;
  row?: ConsentResponse;
  // Scopes a request button asks for, and its accessible name.
  request?: { scopes: ECounselingConsentScope[]; label: string };
};

// The assigned Counselor's media work for one session: consent requests, the governed Record and
// Transcript controls, and their confirmations. Every start, stop and request goes to the COMPASS
// backend, which checks consent, authorization and state before it contacts Daily (ADR-092); the
// browser call object never starts or stops capture. Starts fail closed when consent or the latest
// session state cannot be confirmed; stopping a running capture stays available.
export function useCounselorMedia({
  appointmentId,
  access,
  workspace,
  inCall,
  sessionStateCurrent,
}: {
  appointmentId: string;
  access: ECounselingAccess;
  workspace: CounselorWorkspaceResponse;
  inCall: boolean;
  // False while the latest session refresh failed: the shown state may be out of date.
  sessionStateCurrent: boolean;
}) {
  const queryClient = useQueryClient();
  const consentQuery = useECounselingListAssignedConsents(appointmentId, {
    // While in the call, a Student's answer to a request appears without reloading.
    query: { enabled: access.canManageMediaAssigned, retry: false, refetchInterval: inCall ? 7000 : false },
  });
  const request = useECounselingRequestConsent({ mutation: { retry: false } });
  const startRecording = useECounselingStartAssignedRecording({ mutation: { retry: false } });
  const stopRecording = useECounselingStopAssignedRecording({ mutation: { retry: false } });
  const startTranscription = useECounselingStartAssignedTranscription({ mutation: { retry: false } });
  const stopTranscription = useECounselingStopAssignedTranscription({ mutation: { retry: false } });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pendingStart, setPendingStart] = useState<CaptureKind | null>(null);
  const [storeTranscript, setStoreTranscript] = useState(false);
  const [stopping, setStopping] = useState<Record<CaptureKind, boolean>>({ recording: false, transcription: false });

  const media = workspace.media;
  const isV2 = media.media_policy_version === 2;
  const rows = consentQuery.data?.data.items ?? [];
  const consentsKnown = consentQuery.isSuccess;
  const recordingScope = isV2 ? ECounselingConsentScope.SESSION_MEDIA_CAPTURE : ECounselingConsentScope.AUDIO_VIDEO_RECORDING;
  const transcriptionScope = isV2 ? ECounselingConsentScope.SESSION_MEDIA_CAPTURE : ECounselingConsentScope.LIVE_TRANSCRIPTION;
  const recordingConsent = latestConsent(rows, recordingScope);
  const transcriptionConsent = latestConsent(rows, transcriptionScope);
  const storageConsent = latestConsent(rows, ECounselingConsentScope.TRANSCRIPT_STORAGE);
  const storageApproved = consentsKnown && isEffectivelyApproved(storageConsent);
  const readiness = workspace.provider_readiness;
  const canOperate = access.canManageMediaAssigned && sessionStateCurrent && readiness.daily_enabled && readiness.room_provisioned && readiness.join_allowed;
  const status: Record<CaptureKind, ECounselingCaptureStatus> = {
    recording: media.recording.capture_status,
    transcription: media.transcription.capture_status,
  };
  const canStart: Record<CaptureKind, boolean> = {
    recording: consentsKnown && canOperate && isEffectivelyApproved(recordingConsent) && status.recording === ECounselingCaptureStatus.NOT_STARTED,
    transcription: consentsKnown && canOperate && isEffectivelyApproved(transcriptionConsent) && status.transcription === ECounselingCaptureStatus.NOT_STARTED,
  };
  const canStop: Record<CaptureKind, boolean> = {
    recording: access.canManageMediaAssigned && isLiveOrTransitionalCapture(status.recording),
    transcription: access.canManageMediaAssigned && isLiveOrTransitionalCapture(status.transcription),
  };
  const starting = startRecording.isPending || startTranscription.isPending;
  const requesting = request.isPending;

  // A confirmation whose action is no longer allowed (the Student withdrew, or the state changed)
  // closes; the person reviews the current controls again rather than confirming stale ones.
  if (pendingStart && !starting && !canStart[pendingStart]) {
    setPendingStart(null);
    setError("Media permission or the session changed, so this can’t start now.");
  }

  async function refreshCanonicalState() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getECounselingGetAssignedWorkspaceQueryKey(appointmentId) }),
      queryClient.invalidateQueries({ queryKey: getECounselingListAssignedConsentsQueryKey(appointmentId) }),
    ]);
  }

  async function requestPermission(scopes: ECounselingConsentScope[]) {
    setError(null);
    setNotice(null);
    try {
      await request.mutateAsync({ appointmentId, data: { scopes } });
      setNotice("Request sent to the Student.");
    } catch (caught) {
      setError(ecounselingErrorMessage(caught, "The request couldn’t be sent. The session has been refreshed."));
    }
    await refreshCanonicalState();
  }

  function openStart(kind: CaptureKind) {
    setError(null);
    setNotice(null);
    setStoreTranscript(false);
    leaveFullscreen();
    setPendingStart(kind);
  }

  async function confirmStart() {
    const kind = pendingStart;
    if (!kind || !canStart[kind]) return;
    setError(null);
    try {
      if (kind === "recording") await startRecording.mutateAsync({ appointmentId });
      else await startTranscription.mutateAsync({ appointmentId, data: { store_transcript: storeTranscript && storageApproved } });
    } catch (caught) {
      // Closed rather than retried in place: the refreshed controls show what actually happened.
      setError(ecounselingErrorMessage(caught, kind === "recording"
        ? "Recording couldn’t be started. The session has been refreshed."
        : "Transcription couldn’t be started. The session has been refreshed."));
    }
    setPendingStart(null);
    await refreshCanonicalState();
  }

  async function stop(kind: CaptureKind) {
    setError(null);
    setNotice(null);
    setStopping((current) => ({ ...current, [kind]: true }));
    try {
      if (kind === "recording") await stopRecording.mutateAsync({ appointmentId });
      else await stopTranscription.mutateAsync({ appointmentId });
    } catch (caught) {
      setError(ecounselingErrorMessage(caught, kind === "recording"
        ? "Recording couldn’t be stopped. Try again."
        : "Transcription couldn’t be stopped. Try again."));
    }
    await refreshCanonicalState();
    setStopping((current) => ({ ...current, [kind]: false }));
  }

  // The permission rows the Counselor sees, with the request each one still allows. V1 sessions keep
  // their three separate historical permissions; V2 sessions have one media permission plus
  // transcript storage.
  const projected = (projection: ECounselingConsentStatus) => projectedStates[projection];
  const state = (row: ConsentResponse | undefined, projection: ECounselingConsentStatus) => (consentsKnown ? permissionState(row) : projected(projection));
  const canRequest = consentsKnown && access.canManageMediaAssigned && sessionStateCurrent;
  const permissions: PermissionRow[] = isV2
    ? [
        {
          key: "media",
          subject: "Media permission",
          state: state(recordingConsent, media.recording.consent_status),
          row: recordingConsent,
          request: canRequest && !recordingConsent ? { scopes: [ECounselingConsentScope.SESSION_MEDIA_CAPTURE], label: "Request media permission" } : undefined,
        },
        ...(storageConsent || isViable(recordingConsent) ? [{
          key: "storage",
          subject: "Transcript storage",
          state: state(storageConsent, media.transcription.storage_consent_status),
          row: storageConsent,
          request: canRequest && !storageConsent ? { scopes: [ECounselingConsentScope.TRANSCRIPT_STORAGE], label: "Request transcript storage" } : undefined,
        }] : []),
      ]
    : [
        {
          key: "recording",
          subject: "Recording permission",
          state: state(recordingConsent, media.recording.consent_status),
          row: recordingConsent,
          request: canRequest && !recordingConsent ? { scopes: [ECounselingConsentScope.AUDIO_VIDEO_RECORDING], label: "Request recording permission" } : undefined,
        },
        {
          key: "transcription",
          subject: "Transcription permission",
          state: state(transcriptionConsent, media.transcription.consent_status),
          row: transcriptionConsent,
          request: canRequest && !transcriptionConsent ? { scopes: [ECounselingConsentScope.LIVE_TRANSCRIPTION], label: "Request transcription permission" } : undefined,
        },
        {
          key: "storage",
          subject: "Transcript storage",
          state: state(storageConsent, media.transcription.storage_consent_status),
          row: storageConsent,
          request: canRequest && !storageConsent && isViable(transcriptionConsent) ? { scopes: [ECounselingConsentScope.TRANSCRIPT_STORAGE], label: "Request transcript storage" } : undefined,
        },
      ];

  return {
    isV2,
    access,
    status,
    canStart,
    canStop,
    stopping,
    starting,
    requesting,
    storageApproved,
    consentQuery,
    permissions,
    error,
    notice,
    pendingStart,
    storeTranscript,
    setStoreTranscript,
    sessionStateCurrent,
    inCall,
    captureActive: (["recording", "transcription"] as const).filter((kind) => status[kind] === ECounselingCaptureStatus.ACTIVE || status[kind] === ECounselingCaptureStatus.START_REQUESTED),
    openStart,
    closeStart: () => {
      if (!starting) setPendingStart(null);
    },
    confirmStart,
    stop,
    requestPermission,
  };
}

export type CounselorMedia = ReturnType<typeof useCounselorMedia>;

type Tile = { label: ReactNode; accessibleName?: string; icon: LucideIcon; tone: CallControlTone; disabled: boolean; problem?: boolean; onClick?: () => void; popup?: boolean };

const tileCopy: Record<CaptureKind, { idle: string; stop: string; stopShort: string; done: string; icon: LucideIcon }> = {
  recording: { idle: "Record", stop: "Stop recording", stopShort: "Stop", done: "Recorded", icon: Circle },
  transcription: { idle: "Transcript", stop: "Stop transcript", stopShort: "Stop", done: "Transcribed", icon: ScrollText },
};

// The visible label shortens on a narrow tray; the accessible name always says what stops.
function stopLabel(kind: CaptureKind) {
  return (
    <>
      <span className="@[26rem]/tray:hidden">{tileCopy[kind].stopShort}</span>
      <span className="hidden @[26rem]/tray:inline">{tileCopy[kind].stop}</span>
    </>
  );
}

function captureTile(media: CounselorMedia, kind: CaptureKind): Tile {
  const copy = tileCopy[kind];
  const status = media.status[kind];
  if (media.stopping[kind] || status === ECounselingCaptureStatus.STOP_REQUESTED) {
    return { label: "Stopping…", icon: LoaderCircle, tone: "default", disabled: true };
  }
  if (media.canStop[kind]) {
    return { label: stopLabel(kind), accessibleName: kind === "recording" ? "Stop recording" : "Stop transcription", icon: kind === "recording" ? Square : copy.icon, tone: "live", disabled: false, onClick: () => void media.stop(kind) };
  }
  if (status === ECounselingCaptureStatus.STOPPED || status === ECounselingCaptureStatus.READY) {
    return { label: copy.done, icon: Check, tone: "default", disabled: true };
  }
  if (status === ECounselingCaptureStatus.ERROR) {
    return { label: copy.idle, icon: copy.icon, tone: "default", disabled: true, problem: true };
  }
  return {
    label: copy.idle,
    accessibleName: kind === "recording" ? "Start recording" : "Start transcription",
    icon: copy.icon,
    tone: "default",
    disabled: !media.canStart[kind] || media.starting,
    popup: true,
    onClick: () => media.openStart(kind),
  };
}

// Record and Transcript in the call tray. They look like part of the call but act through the
// COMPASS backend (useCounselorMedia).
export function GovernedCaptureControls({ media }: { media: CounselorMedia }) {
  if (!media.access.canManageMediaAssigned) return null;
  return (
    <>
      {(["recording", "transcription"] as const).map((kind) => {
        const tile = captureTile(media, kind);
        return (
          <CallControl
            key={kind}
            icon={tile.icon}
            label={tile.label}
            accessibleName={tile.accessibleName}
            tone={tile.tone}
            problem={tile.problem}
            disabled={tile.disabled}
            aria-haspopup={tile.popup ? "dialog" : undefined}
            onClick={tile.onClick}
            className={tile.icon === LoaderCircle ? "[&>svg]:animate-spin [&>svg]:motion-reduce:animate-none" : undefined}
          />
        );
      })}
    </>
  );
}

function PermissionItem({ permission, busy, onRequest }: { permission: PermissionRow; busy: boolean; onRequest: (scopes: ECounselingConsentScope[]) => void }) {
  const copy = permissionCopy[permission.state];
  const Icon = copy.icon;
  return (
    <li className="flex min-h-9 flex-wrap items-center gap-x-3 gap-y-1">
      <span className={cn("inline-flex items-center gap-1.5 text-sm font-medium", copy.tone)}>
        <Icon aria-hidden="true" size={16} />
        {copy.text(permission.subject)}
      </span>
      {permission.request ? (
        <Button variant="secondary" className="min-h-9 px-3 py-1" disabled={busy} aria-label={permission.request.label} onClick={() => onRequest(permission.request!.scopes)}>
          Request
        </Button>
      ) : null}
    </li>
  );
}

// The compact media strip under the call: permission state and requests, capture problems, a stop
// for capture still running when this person is not in the call, and the outcome of the last media
// action. Request and decision times are under Details.
export function CounselorMediaStrip({ media }: { media: CounselorMedia }) {
  if (!media.access.canManageMediaAssigned) {
    return <p className="px-3 py-2.5 text-sm text-muted sm:px-4">Media controls are unavailable to this account.</p>;
  }
  const { consentQuery } = media;
  const problems = (["recording", "transcription"] as const).filter((kind) => media.status[kind] === ECounselingCaptureStatus.ERROR);
  const stopOutsideCall = media.inCall ? [] : (["recording", "transcription"] as const).filter((kind) => media.canStop[kind]);
  const withTimes = media.permissions.filter((permission) => permission.row);
  return (
    <div className="space-y-2 px-3 py-2.5 sm:px-4">
      {consentQuery.isPending ? (
        <div aria-busy="true"><span className="sr-only">Loading media permission…</span><Skeleton className="h-6 w-2/3" /></div>
      ) : consentQuery.isError ? (
        <div role="alert" className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-danger">
          <span>Media permission couldn’t be loaded. Recording and transcription can’t start until it loads.</span>
          <Button variant="secondary" className="min-h-9 px-3 py-1" onClick={() => void consentQuery.refetch()}>Retry</Button>
        </div>
      ) : null}
      <ul aria-label="Media permission" className="flex flex-wrap gap-x-6 gap-y-1">
        {media.permissions.map((permission) => (
          <PermissionItem key={permission.key} permission={permission} busy={media.requesting} onRequest={(scopes) => void media.requestPermission(scopes)} />
        ))}
      </ul>
      {!media.sessionStateCurrent ? (
        <p role="status" className="text-sm text-muted">Session status couldn’t be refreshed. Starting recording or transcription is paused until it’s back.</p>
      ) : null}
      {problems.map((kind) => (
        <p key={kind} className="text-sm font-medium text-danger">{kind === "recording" ? "Recording" : "Transcription"} · {captureStatusLabel(ECounselingCaptureStatus.ERROR)}</p>
      ))}
      {stopOutsideCall.length ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-ink">Still running while you’re out of the call:</span>
          {stopOutsideCall.map((kind) => (
            <Button key={kind} variant="secondary" className="min-h-9 px-3 py-1" disabled={media.stopping[kind]} onClick={() => void media.stop(kind)}>
              {media.stopping[kind] ? "Stopping…" : kind === "recording" ? "Stop recording" : "Stop transcription"}
            </Button>
          ))}
        </div>
      ) : null}
      {media.error && !media.pendingStart ? <p role="alert" className="text-sm text-danger">{media.error}</p> : null}
      {media.notice ? <p role="status" className="text-sm text-success">{media.notice}</p> : null}
      {withTimes.length ? (
        <Disclosure summary="Details" summaryClassName="min-h-9">
          <ul className="space-y-1 pb-1 text-xs text-muted">
            {withTimes.map((permission) => (
              <li key={permission.key}>
                {permission.subject}: requested {formatECounselingDateTime(permission.row!.requested_at)}
                {permission.row!.decided_at ? ` · decided ${formatECounselingDateTime(permission.row!.decided_at)}` : ""}
                {permission.row!.withdrawn_at ? ` · withdrawn ${formatECounselingDateTime(permission.row!.withdrawn_at)}` : ""}
              </li>
            ))}
          </ul>
        </Disclosure>
      ) : null}
    </div>
  );
}

function TranscriptChoice({ media }: { media: CounselorMedia }) {
  const name = useId();
  if (!media.storageApproved) {
    return <p className="text-sm text-ink">Live transcription only. The student hasn’t allowed transcript storage, so no transcript file is saved.</p>;
  }
  const options = [
    { value: false, label: "Live transcription only", hint: "No transcript file is saved." },
    {
      value: true,
      label: "Live transcription + save transcript",
      hint: media.isV2 ? "The transcript is saved and may be downloaded by an authorized assigned Counselor." : "The transcript is stored by the video service.",
    },
  ];
  return (
    <fieldset>
      <legend className="text-sm font-semibold text-ink">Transcript</legend>
      <div className="mt-2 space-y-2">
        {options.map((option) => (
          <label key={String(option.value)} className="flex cursor-pointer items-start gap-3 rounded-md border border-border px-3 py-2.5 has-[:checked]:border-brand has-[:checked]:bg-brand-subtle has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-focus">
            <input
              type="radio"
              name={name}
              className="mt-1 size-4 accent-brand focus-visible:outline-none"
              checked={media.storeTranscript === option.value}
              disabled={media.starting}
              onChange={() => media.setStoreTranscript(option.value)}
            />
            <span>
              <span className="block text-sm font-semibold text-ink">{option.label}</span>
              <span className="block text-sm text-muted">{option.hint}</span>
            </span>
          </label>
        ))}
      </div>
      <p className="mt-2 text-sm text-muted">The student has allowed transcript storage.</p>
    </fieldset>
  );
}

// The confirmations for starting capture. Their wording is the consequence the Counselor reviews
// at the moment of the decision; it is not repeated elsewhere on the page.
export function CaptureStartDialogs({ media }: { media: CounselorMedia }) {
  const recording = media.pendingStart === "recording";
  return (
    <ConsequentialActionDialog
      open={media.pendingStart !== null}
      title={recording ? "Start recording?" : "Start live transcription?"}
      confirmLabel={recording ? "Start recording" : "Start transcription"}
      pendingLabel="Starting…"
      pending={media.starting}
      error={null}
      onOpenChange={(open) => {
        if (!open) media.closeStart();
      }}
      onConfirm={() => void media.confirmStart()}
      choices={!recording && media.pendingStart ? <TranscriptChoice media={media} /> : undefined}
    >
      {recording ? (
        media.isV2 ? (
          <>
            <p>Audio and video from this session will be recorded.</p>
            <p>The student has approved media permission. The completed recording will be saved and may be downloaded by an authorized assigned Counselor.</p>
          </>
        ) : (
          <p>Audio and video from this session will be recorded. The student has approved recording.</p>
        )
      ) : (
        <p>Speech is processed as text while transcription is on. Transcript text isn’t shown here.</p>
      )}
    </ConsequentialActionDialog>
  );
}
