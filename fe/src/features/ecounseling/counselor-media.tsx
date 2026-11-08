"use client";

import { useConfirmedECounselingConsent, usePendingECounselingMedia } from "./consent-freshness-provider";

import { Check, Circle, Clock, LoaderCircle, Square, X, type LucideIcon } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Disclosure } from "@/components/ui/disclosure";
import { Skeleton } from "@/components/ui/skeleton";
import { CallControl, type CallControlTone } from "@/features/ecounseling/call/call-control";
import { leaveFullscreen } from "@/features/ecounseling/call/use-fullscreen";
import type { ECounselingAccess } from "@/features/ecounseling/ecounseling-access";
import { useCaptureStop, type CaptureKind } from "@/features/ecounseling/use-capture-stop";
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
} from "@/lib/api/generated/e-counseling/e-counseling";
import {
  ECounselingCaptureStatus,
  ECounselingConsentDecision,
  ECounselingConsentScope,
  type ConsentResponse,
  type CounselorWorkspaceResponse,
  ECounselingConsentStatus,
} from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";
import { captureSafetyState, stopControlState } from "./runtime/runtime-model";


function latestConsent(rows: ConsentResponse[], scope: ECounselingConsentScope): ConsentResponse | undefined {
  return rows.filter((item) => item.scope === scope).sort((a, b) => b.requested_at.localeCompare(a.requested_at))[0];
}

function isEffectivelyApproved(row: ConsentResponse | undefined): boolean {
  return Boolean(row?.effective && row.decision === ECounselingConsentDecision.APPROVED && !row.withdrawn_at);
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
  "not-requested": { text: (subject) => `${subject} · Not requested`, icon: Circle, tone: "text-muted" },
  pending: { text: (subject) => `${subject} · Waiting for Student`, icon: Clock, tone: "text-ink" },
  approved: { text: (subject) => `${subject} · Approved`, icon: Check, tone: "text-success" },
  invalid: { text: (subject) => `${subject} · No longer valid`, icon: X, tone: "text-muted" },
  declined: { text: (subject) => `${subject} · Declined`, icon: X, tone: "text-muted" },
  withdrawn: { text: (subject) => `${subject} · Withdrawn`, icon: X, tone: "text-muted" },
};

type PermissionRow = {
  key: string;
  subject: string;
  state: PermissionState;
  row?: ConsentResponse;
  // Scopes a request button asks for, and its accessible name.
  request?: { scopes: ECounselingConsentScope[]; label: string };
};

// The assigned Counselor's recording work for one session: the consent request, the governed Record
// control, and its confirmation. Every start, stop and request goes to the COMPASS
// backend, which checks consent, authorization and state before it contacts Daily (ADR-092); the
// browser call object never starts or stops capture. Starts fail closed when consent or the latest
// session state cannot be confirmed; stopping a running capture stays available.
export function useCounselorMedia({
  appointmentId,
  access,
  workspace,
  inCall,
  sessionStateCurrent: suppliedSessionStateCurrent,
}: {
  appointmentId: string;
  access: ECounselingAccess;
  workspace: CounselorWorkspaceResponse;
  inCall: boolean;
  // False while the latest session refresh failed: the shown state may be out of date.
  sessionStateCurrent: boolean;
}) {
  const queryClient = useQueryClient();
  const workspacePending = usePendingECounselingMedia(appointmentId);
  const sessionStateCurrent = suppliedSessionStateCurrent && !workspacePending;
  const consentQuery = useECounselingListAssignedConsents(appointmentId, {
    // One portal coordinator refreshes consent both before and during the call.
    query: { enabled: access.canManageMediaAssigned, retry: false, refetchInterval: false },
  });
  const request = useECounselingRequestConsent({ mutation: { retry: false } });
  const startRecording = useECounselingStartAssignedRecording({ mutation: { retry: false } });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pendingStart, setPendingStart] = useState<CaptureKind | null>(null);
  const capture = useCaptureStop(appointmentId, () => refreshCanonicalState());

  const media = workspace.media;
  const rows = consentQuery.data?.data.items ?? [];
  const consentsKnown = useConfirmedECounselingConsent(appointmentId, getECounselingListAssignedConsentsQueryKey(appointmentId));
  const recordingConsent = latestConsent(rows, ECounselingConsentScope.AUDIO_VIDEO_RECORDING);
  const readiness = workspace.provider_readiness;
  const canOperate = access.canManageMediaAssigned && sessionStateCurrent && readiness.daily_enabled && readiness.room_provisioned && readiness.join_allowed;
  const status: Record<CaptureKind, ECounselingCaptureStatus> = { recording: media.recording.capture_status };
  const canStart: Record<CaptureKind, boolean> = {
    recording: consentsKnown && canOperate && media.recording.consent_status === ECounselingConsentStatus.APPROVED && isEffectivelyApproved(recordingConsent) && status.recording === ECounselingCaptureStatus.NOT_STARTED,
  };
  const canStop: Record<CaptureKind, boolean> = {
    recording: access.canManageMediaAssigned && isLiveOrTransitionalCapture(status.recording),
  };
  const starting = startRecording.isPending;
  const requesting = request.isPending;

  // A confirmation whose action is no longer allowed (the Student withdrew, or the state changed)
  // closes; the person reviews the current controls again rather than confirming stale ones.
  if (pendingStart && !starting && !canStart[pendingStart]) {
    setPendingStart(null);
    setError("Recording permission or the session changed, so this can’t start now.");
  }

  async function refreshCanonicalState() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getECounselingGetAssignedWorkspaceQueryKey(appointmentId) }, { cancelRefetch: false }),
      queryClient.invalidateQueries({ queryKey: getECounselingListAssignedConsentsQueryKey(appointmentId) }, { cancelRefetch: false }),
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
    leaveFullscreen();
    setPendingStart(kind);
  }

  async function confirmStart() {
    const kind = pendingStart;
    if (!kind || !canStart[kind]) return;
    setError(null);
    try {
      await startRecording.mutateAsync({ appointmentId });
    } catch (caught) {
      // Closed rather than retried in place: the refreshed controls show what actually happened.
      setError(ecounselingErrorMessage(caught, "Recording couldn’t be started. The session has been refreshed."));
    }
    setPendingStart(null);
    await refreshCanonicalState();
  }

  async function stop(kind: CaptureKind) {
    setError(null);
    setNotice(null);
    await capture.stop(kind);
  }

  // The one permission row the Counselor sees, with the request it still allows.
  const projected = (projection: ECounselingConsentStatus) => projectedStates[projection];
  // Denial/withdrawal cannot be reopened. A terminal workspace projection must not be
  // presented as valid permission just because an older consent-list read said APPROVED.
  const state = (row: ConsentResponse | undefined, projection: ECounselingConsentStatus) => (
    !consentsKnown || projection === ECounselingConsentStatus.DENIED || projection === ECounselingConsentStatus.WITHDRAWN
      ? projected(projection)
      : permissionState(row)
  );
  const canRequest = consentsKnown && access.canManageMediaAssigned && sessionStateCurrent;
  const permissions: PermissionRow[] = [
    {
      key: "recording",
      subject: "Recording permission",
      state: state(recordingConsent, media.recording.consent_status),
      row: recordingConsent,
      request: canRequest && !recordingConsent ? { scopes: [ECounselingConsentScope.AUDIO_VIDEO_RECORDING], label: "Request recording permission" } : undefined,
    },
  ];

  return {
    access,
    status,
    canStart,
    canStop,
    stopping: capture.stopping,
    stopFailed: capture.failed,
    starting,
    requesting,
    consentQuery,
    permissions,
    error: error ?? capture.error,
    notice,
    pendingStart,
    sessionStateCurrent,
    inCall,
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
  const stopState = stopControlState(status, { stopping: media.stopping[kind], failed: media.stopFailed[kind] });
  if (stopState === "stopping") {
    return { label: "Stopping…", icon: LoaderCircle, tone: "default", disabled: true };
  }
  if (stopState === "not-confirmed") {
    // COMPASS still records Stop intent, but this request failed: capture may still be running.
    return { label: "Stop not confirmed", accessibleName: "Recording stop not confirmed. Stop recording again", icon: Square, tone: "live", disabled: false, problem: true, onClick: () => void media.stop(kind) };
  }
  if (media.canStop[kind]) {
    return { label: stopLabel(kind), accessibleName: "Stop recording", icon: Square, tone: "live", disabled: false, onClick: () => void media.stop(kind) };
  }
  if (captureSafetyState(status) === "uncertain") {
    return { label: "Status uncertain", accessibleName: "Recording status uncertain", icon: copy.icon, tone: "default", disabled: true, problem: true };
  }
  if (status === ECounselingCaptureStatus.STOPPED || status === ECounselingCaptureStatus.READY) {
    return { label: copy.done, icon: Check, tone: "default", disabled: true };
  }
  if (status === ECounselingCaptureStatus.ERROR) {
    return { label: copy.idle, icon: copy.icon, tone: "default", disabled: true, problem: true };
  }
  return {
    label: copy.idle,
    accessibleName: "Start recording",
    icon: copy.icon,
    tone: "default",
    disabled: !media.canStart[kind] || media.starting,
    popup: true,
    onClick: () => media.openStart(kind),
  };
}

// Record in the call tray. It looks like part of the call but acts through the COMPASS backend
// (useCounselorMedia).
export function GovernedCaptureControls({ media }: { media: CounselorMedia }) {
  if (!media.access.canManageMediaAssigned) return null;
  return (
    <>
      {(["recording"] as const).map((kind) => {
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
  const problems = (["recording"] as const).filter((kind) => captureSafetyState(media.status[kind]) === "uncertain");
  const stopOutsideCall = media.inCall ? [] : (["recording"] as const).filter((kind) => media.canStop[kind]);
  const withTimes = media.permissions.filter((permission) => permission.row);
  return (
    <div className="space-y-2 px-3 py-2.5 sm:px-4">
      {consentQuery.isPending ? (
        <div aria-busy="true"><span className="sr-only">Loading recording permission…</span><Skeleton className="h-6 w-2/3" /></div>
      ) : consentQuery.isError ? (
        <div role="alert" className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-danger">
          <span>Recording permission couldn’t be loaded. Recording can’t start until it loads.</span>
          <Button variant="secondary" className="min-h-9 px-3 py-1" onClick={() => void consentQuery.refetch()}>Retry</Button>
        </div>
      ) : null}
      {!media.sessionStateCurrent ? (
        <p role="alert" className="text-sm font-medium text-danger">Session status couldn’t be refreshed. Starting recording is paused until it’s back.</p>
      ) : null}
      {problems.map((kind) => (
        <p key={kind} role="alert" className="text-sm font-semibold text-danger">Recording · {captureStatusLabel(media.status[kind], kind)}. Stopping has not been confirmed.</p>
      ))}
      {stopOutsideCall.length ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-danger">Stopping has not been confirmed:</span>
          {stopOutsideCall.map((kind) => (
            <Button key={kind} variant="secondary" className="min-h-11 px-3 py-1" disabled={media.stopping[kind]} onClick={() => void media.stop(kind)}>
              {media.stopping[kind] ? "Stopping…" : "Stop recording"}
            </Button>
          ))}
        </div>
      ) : null}
      {media.error && !media.pendingStart ? <p role="alert" className="text-sm font-medium text-danger">{media.error}</p> : null}
      <ul aria-label="Recording permission" className="flex flex-wrap gap-x-6 gap-y-1">
        {media.permissions.map((permission) => (
          <PermissionItem key={permission.key} permission={permission} busy={media.requesting} onRequest={(scopes) => void media.requestPermission(scopes)} />
        ))}
      </ul>
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

// The confirmation for starting a recording. Its wording is the consequence the Counselor reviews
// at the moment of the decision; it is not repeated elsewhere on the page.
export function CaptureStartDialogs({ media }: { media: CounselorMedia }) {
  return (
    <ConsequentialActionDialog
      open={media.pendingStart !== null}
      title="Start recording?"
      confirmLabel="Start recording"
      pendingLabel="Starting…"
      pending={media.starting}
      error={null}
      onOpenChange={(open) => {
        if (!open) media.closeStart();
      }}
      onConfirm={() => void media.confirmStart()}
    >
      <p>Audio and video from this session will be recorded.</p>
      <p>The student has allowed recording. The completed recording will be saved privately and may be downloaded by the assigned Counselor.</p>
    </ConsequentialActionDialog>
  );
}
