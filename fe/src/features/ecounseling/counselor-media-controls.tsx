"use client";

import { useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Label } from "@/components/ui/label";
import { Panel, PanelHeader, PanelMessage, PanelSection } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ECounselingCaptureStatus,
  ECounselingConsentDecision,
  ECounselingConsentScope,
  type ECounselingConsentStatus,
  type ConsentResponse,
  type CounselorWorkspaceResponse,
} from "@/lib/api/generated/model";
import type { ECounselingAccess } from "@/features/ecounseling/ecounseling-access";
import { CaptureState } from "@/features/ecounseling/session-stage";
import {
  consentProjectionLabels,
  consentStatusLabel,
  ecounselingErrorMessage,
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

type StartAction = "recording" | "transcription";

function consentRowsLabel(rows: ConsentResponse[], scope: ECounselingConsentScope): string {
  const row = latestConsent(rows, scope);
  return row ? consentStatusLabel(row) : "Not requested";
}

function latestConsent(rows: ConsentResponse[], scope: ECounselingConsentScope): ConsentResponse | undefined {
  return rows.filter((item) => item.scope === scope).sort((a, b) => b.requested_at.localeCompare(a.requested_at))[0];
}

function rowFor(rows: ConsentResponse[], scope: ECounselingConsentScope): ConsentResponse | undefined {
  return latestConsent(rows, scope);
}

function isViable(row: ConsentResponse | undefined): boolean {
  return Boolean(
    row &&
      !row.withdrawn_at &&
      (row.decision === ECounselingConsentDecision.PENDING ||
        (row.decision === ECounselingConsentDecision.APPROVED && row.effective)),
  );
}

function isEffectivelyApproved(row: ConsentResponse | undefined): boolean {
  return Boolean(
    row?.effective && row.decision === ECounselingConsentDecision.APPROVED && !row.withdrawn_at,
  );
}

function MediaFacts({ facts }: { facts: Array<[string, ReactNode]> }) {
  return (
    <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
      {facts.map(([label, value]) => (
        <div key={label} className="min-w-0">
          <dt className="text-xs font-semibold text-muted">{label}</dt>
          <dd className="mt-0.5 text-sm text-ink">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function CounselorMediaControls({
  appointmentId,
  access,
  workspace,
}: {
  appointmentId: string;
  access: ECounselingAccess;
  workspace: CounselorWorkspaceResponse;
}) {
  const queryClient = useQueryClient();
  const consentQuery = useECounselingListAssignedConsents(appointmentId, {
    query: { enabled: access.canManageMediaAssigned, retry: false },
  });
  const request = useECounselingRequestConsent({ mutation: { retry: false } });
  const startRecording = useECounselingStartAssignedRecording({ mutation: { retry: false } });
  const stopRecording = useECounselingStopAssignedRecording({ mutation: { retry: false } });
  const startTranscription = useECounselingStartAssignedTranscription({ mutation: { retry: false } });
  const stopTranscription = useECounselingStopAssignedTranscription({ mutation: { retry: false } });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pendingStart, setPendingStart] = useState<StartAction | null>(null);
  const [storeTranscript, setStoreTranscript] = useState(false);
  const busy = request.isPending || startRecording.isPending || stopRecording.isPending || startTranscription.isPending || stopTranscription.isPending;
  const rows = consentQuery.data?.data.items ?? [];
  const canReadConsents = consentQuery.isSuccess;
  const recordingConsent = rowFor(rows, ECounselingConsentScope.AUDIO_VIDEO_RECORDING);
  const transcriptionConsent = rowFor(rows, ECounselingConsentScope.LIVE_TRANSCRIPTION);
  const storageConsent = rowFor(rows, ECounselingConsentScope.TRANSCRIPT_STORAGE);
  const recordingApproved = isEffectivelyApproved(recordingConsent);
  const transcriptionApproved = isEffectivelyApproved(transcriptionConsent);
  const storageApproved = isEffectivelyApproved(storageConsent);
  const recordingStatus = workspace.media.recording.capture_status;
  const transcriptionStatus = workspace.media.transcription.capture_status;
  const canOperate = access.canManageMediaAssigned && workspace.provider_readiness.daily_enabled && workspace.provider_readiness.room_provisioned && workspace.provider_readiness.join_allowed;
  const recordingCanStart = canReadConsents && canOperate && recordingApproved && recordingStatus === ECounselingCaptureStatus.NOT_STARTED;
  const recordingCanStop = access.canManageMediaAssigned && isLiveOrTransitionalCapture(recordingStatus);
  const transcriptionCanStart = canReadConsents && canOperate && transcriptionApproved && transcriptionStatus === ECounselingCaptureStatus.NOT_STARTED && (storeTranscript ? storageApproved : true);
  const transcriptionCanStop = access.canManageMediaAssigned && isLiveOrTransitionalCapture(transcriptionStatus);
  const hasLiveTranscriptionRequest = isViable(transcriptionConsent);
  const noRecordingRequest = !recordingConsent;
  const noTranscriptionRequest = !transcriptionConsent;
  const noStorageRequest = !storageConsent;

  async function refreshCanonicalState() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getECounselingGetAssignedWorkspaceQueryKey(appointmentId) }),
      queryClient.invalidateQueries({ queryKey: getECounselingListAssignedConsentsQueryKey(appointmentId) }),
    ]);
  }

  async function runCommand(command: () => Promise<unknown>, successMessage?: string, fallback = "The video service could not confirm this change.") {
    setError(null);
    setNotice(null);
    try {
      await command();
      if (successMessage) setNotice(successMessage);
    } catch (caught) {
      setError(ecounselingErrorMessage(caught, fallback));
    }
    await refreshCanonicalState();
  }

  async function requestConsent(scopes: ECounselingConsentScope[]) {
    await runCommand(
      () => request.mutateAsync({ appointmentId, data: { scopes } }),
      "Consent request sent to the Student.",
      "The consent request could not be saved. The session has been refreshed.",
    );
  }

  async function confirmStartAction() {
    const selected = pendingStart;
    if (!selected) return;
    setError(null);
    setNotice(null);
    try {
      if (selected === "recording") {
        await startRecording.mutateAsync({ appointmentId });
      } else {
        await startTranscription.mutateAsync({
          appointmentId,
          data: { store_transcript: storeTranscript },
        });
      }
      setPendingStart(null);
    } catch (caught) {
      setError(
        ecounselingErrorMessage(
          caught,
          selected === "recording"
            ? "Recording could not be started. The session has been refreshed."
            : "Transcription could not be started. The session has been refreshed.",
        ),
      );
    }
    await refreshCanonicalState();
  }

  const consentLabel = (scope: ECounselingConsentScope, projection: ECounselingConsentStatus) =>
    canReadConsents ? consentRowsLabel(rows, scope) : consentProjectionLabels[projection];
  const providerNote = !workspace.provider_readiness.daily_enabled
    ? "Video sessions are not enabled, so recording and transcription are unavailable. Counseling is unaffected."
    : !workspace.provider_readiness.room_provisioned || !workspace.provider_readiness.join_allowed
      ? "Recording and transcription become available when the session can be joined."
      : null;

  return (
    <Panel aria-labelledby="e-counseling-media-controls-heading">
      <PanelHeader
        title="Media controls"
        titleId="e-counseling-media-controls-heading"
        description="Consent and capture are separate. Recording or transcription starts only when you start it, after the Student’s consent for it is effective."
      />
      {providerNote ? <p className="border-b border-brand-line px-4 py-3 text-sm text-muted sm:px-5">{providerNote}</p> : null}
      {access.canManageMediaAssigned ? consentQuery.isPending ? (
        <div aria-busy="true" className="px-4 pt-4 sm:px-5"><span className="sr-only">Loading session consent controls…</span><Skeleton className="h-16 w-full" /></div>
      ) : consentQuery.isError ? (
        <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void consentQuery.refetch()}>Retry consent state</Button>}>
          Consent state could not be loaded. New requests and starts are unavailable; an active capture can still be stopped.
        </PanelMessage>
      ) : null : <PanelMessage>Media controls and consent details are unavailable to this account.</PanelMessage>}
      {access.canManageMediaAssigned ? <>
        <PanelSection title="Audio/video recording" titleId="recording-controls-heading" level={3}>
          <MediaFacts facts={[
            ["Consent", consentLabel(ECounselingConsentScope.AUDIO_VIDEO_RECORDING, workspace.media.recording.consent_status)],
            ["Status", <CaptureState key="capture" status={recordingStatus} live="recording" />],
          ]} />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {canReadConsents && noRecordingRequest ? <Button variant="secondary" disabled={busy} onClick={() => void requestConsent([ECounselingConsentScope.AUDIO_VIDEO_RECORDING])}>Request recording consent</Button> : null}
            {recordingCanStart ? <Button disabled={busy} onClick={() => setPendingStart("recording")}>Start recording</Button> : null}
            {recordingCanStop ? <Button variant="secondary" disabled={busy} onClick={() => void runCommand(() => stopRecording.mutateAsync({ appointmentId }))}>Stop recording</Button> : null}
            {!recordingCanStart && recordingStatus === ECounselingCaptureStatus.NOT_STARTED && !recordingApproved ? <p className="basis-full text-sm text-muted">Recording can start only after the Student’s recording consent is effective.</p> : null}
            {recordingStatus === ECounselingCaptureStatus.READY ? <p role="status" className="basis-full text-sm text-muted">{workspace.media.recording.artifact_disposed_at ? "The provider recording was disposed under an approved retention rule." : "Recording completed."}</p> : null}
          </div>
        </PanelSection>
        <PanelSection title="Session transcription" titleId="transcription-controls-heading" level={3}>
          <MediaFacts facts={[
            ["Consent", consentLabel(ECounselingConsentScope.LIVE_TRANSCRIPTION, workspace.media.transcription.consent_status)],
            ["Storage consent", consentLabel(ECounselingConsentScope.TRANSCRIPT_STORAGE, workspace.media.transcription.storage_consent_status)],
            ["Status", <CaptureState key="capture" status={transcriptionStatus} live="transcription" />],
            ["Transcript storage", workspace.media.transcription.storage_enabled ? "On for this transcription" : "Off"],
          ]} />
          {transcriptionCanStart && storageApproved && transcriptionStatus === ECounselingCaptureStatus.NOT_STARTED ? <div className="mt-3 flex items-start gap-3"><input id="e-counseling-store-transcript" type="checkbox" checked={storeTranscript} disabled={busy} onChange={(event) => setStoreTranscript(event.target.checked)} className="mt-1 size-4 rounded border border-border accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" /><div><Label htmlFor="e-counseling-store-transcript">Store transcript for this session</Label><p className="mt-1 text-sm text-muted">Optional and off by default. This choice must be made before transcription starts.</p></div></div> : null}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {canReadConsents && noTranscriptionRequest ? <><Button variant="secondary" disabled={busy} onClick={() => void requestConsent([ECounselingConsentScope.LIVE_TRANSCRIPTION])}>Request transcription consent</Button>{noStorageRequest ? <Button variant="secondary" disabled={busy} onClick={() => void requestConsent([ECounselingConsentScope.LIVE_TRANSCRIPTION, ECounselingConsentScope.TRANSCRIPT_STORAGE])}>Request transcription + storage consent</Button> : null}</> : null}
            {canReadConsents && hasLiveTranscriptionRequest && noStorageRequest ? <Button variant="secondary" disabled={busy} onClick={() => void requestConsent([ECounselingConsentScope.TRANSCRIPT_STORAGE])}>Request transcript-storage consent</Button> : null}
            {transcriptionCanStart ? <Button disabled={busy} onClick={() => setPendingStart("transcription")}>Start transcription</Button> : null}
            {transcriptionCanStop ? <Button variant="secondary" disabled={busy} onClick={() => void runCommand(() => stopTranscription.mutateAsync({ appointmentId }))}>Stop transcription</Button> : null}
            {!transcriptionCanStart && transcriptionStatus === ECounselingCaptureStatus.NOT_STARTED && !transcriptionApproved ? <p className="basis-full text-sm text-muted">Transcription can start only after the Student’s transcription consent is effective.</p> : null}
            {transcriptionApproved && !storageApproved && transcriptionStatus === ECounselingCaptureStatus.NOT_STARTED ? <p className="basis-full text-sm text-muted">Transcription may run without storage consent. Transcript storage is optional.</p> : null}
            {transcriptionStatus === ECounselingCaptureStatus.READY ? <p role="status" className="basis-full text-sm text-muted">{workspace.media.transcription.artifact_disposed_at ? "The stored transcript was disposed under an approved retention rule." : "Transcription completed. Transcript text and playback are not available in COMPASS."}</p> : null}
          </div>
        </PanelSection>
      </> : null}
      {(error && !pendingStart) || notice ? (
        <div className="border-t border-brand-line px-4 py-3 sm:px-5">
          {error && !pendingStart ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
          {notice ? <p role="status" className="text-sm text-success">{notice}</p> : null}
        </div>
      ) : null}
      <ConsequentialActionDialog
        open={Boolean(pendingStart)}
        title={
          pendingStart === "recording"
            ? "Start audio/video recording?"
            : "Start session transcription?"
        }
        confirmLabel={
          pendingStart === "recording"
            ? "Start recording"
            : "Start transcription"
        }
        pendingLabel="Starting…"
        pending={busy}
        error={error}
        onOpenChange={(open) => {
          if (!open) setPendingStart(null);
        }}
        onConfirm={() => void confirmStartAction()}
      >
        <p>
          {pendingStart === "recording"
            ? "Recording will start only because the Student has currently approved this session’s recording consent."
            : storeTranscript
              ? "Speech will be processed as text while transcription is active. Transcript storage is enabled for this transcription because the Student has approved both transcription and transcript storage. COMPASS does not display or provide transcript text."
              : "Speech will be processed as text while transcription is active. COMPASS does not display or provide transcript text."}
        </p>
      </ConsequentialActionDialog>
    </Panel>
  );
}
