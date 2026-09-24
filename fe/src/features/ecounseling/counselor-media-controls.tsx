"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import type { ConsentResponse } from "@/lib/api/generated/model";
import type { ECounselingAccess } from "@/features/ecounseling/ecounseling-access";
import { captureStatusLabel, consentStatusLabel, ECounselingScope, ecounselingErrorMessage } from "@/features/ecounseling/ecounseling-shared";
import type { CounselorWorkspaceResponse } from "@/lib/api/generated/model";
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

function consentRowsLabel(rows: ConsentResponse[], scope: string): string {
  const row = latestConsent(rows, scope);
  return row ? consentStatusLabel(row) : "Not requested";
}

function latestConsent(rows: ConsentResponse[], scope: string): ConsentResponse | undefined {
  return rows.filter((item) => item.scope === scope).sort((a, b) => b.requested_at.localeCompare(a.requested_at))[0];
}

function rowFor(rows: ConsentResponse[], scope: string): ConsentResponse | undefined {
  return latestConsent(rows, scope);
}

function isViable(row: { decision: string; effective: boolean; withdrawn_at: string | null } | undefined): boolean {
  return Boolean(row && !row.withdrawn_at && (row.decision === "PENDING" || (row.decision === "APPROVED" && row.effective)));
}

function projectedConsentLabel(value: string): string {
  if (!value || value === "NOT_REQUESTED") return "Not requested";
  if (value === "APPROVED") return "Approved";
  if (value === "PENDING") return "Pending";
  if (value === "DENIED") return "Declined";
  if (value === "WITHDRAWN") return "Withdrawn";
  return value.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
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
  const recordingConsent = rowFor(rows, ECounselingScope.recording);
  const transcriptionConsent = rowFor(rows, ECounselingScope.transcription);
  const storageConsent = rowFor(rows, ECounselingScope.storage);
  const recordingApproved = Boolean(recordingConsent?.effective && recordingConsent.decision === "APPROVED" && !recordingConsent.withdrawn_at);
  const transcriptionApproved = Boolean(transcriptionConsent?.effective && transcriptionConsent.decision === "APPROVED" && !transcriptionConsent.withdrawn_at);
  const storageApproved = Boolean(storageConsent?.effective && storageConsent.decision === "APPROVED" && !storageConsent.withdrawn_at);
  const recordingStatus = workspace.media.recording.capture_status;
  const transcriptionStatus = workspace.media.transcription.capture_status;
  const canOperate = access.canManageMediaAssigned && workspace.provider_readiness.daily_enabled && workspace.provider_readiness.room_provisioned && workspace.provider_readiness.join_allowed;
  const recordingCanStart = canReadConsents && canOperate && recordingApproved && recordingStatus === "NOT_STARTED";
  const recordingCanStop = access.canManageMediaAssigned && ["START_REQUESTED", "ACTIVE", "STOP_REQUESTED"].includes(recordingStatus);
  const transcriptionCanStart = canReadConsents && canOperate && transcriptionApproved && transcriptionStatus === "NOT_STARTED" && (storeTranscript ? storageApproved : true);
  const transcriptionCanStop = access.canManageMediaAssigned && ["START_REQUESTED", "ACTIVE", "STOP_REQUESTED"].includes(transcriptionStatus);
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

  async function runCommand(command: () => Promise<unknown>, successMessage?: string, fallback = "The provider could not confirm this media control.") {
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

  async function requestConsent(scopes: string[]) {
    await runCommand(
      () => request.mutateAsync({ appointmentId, data: { scopes } }),
      "Consent request sent to the Student.",
      "The consent request could not be saved. The current session state has been refreshed.",
    );
  }

  async function confirmStartAction() {
    const selected = pendingStart;
    if (!selected) return;
    setPendingStart(null);
    if (selected === "recording") {
      await runCommand(() => startRecording.mutateAsync({ appointmentId }));
    } else {
      await runCommand(() => startTranscription.mutateAsync({ appointmentId, data: { store_transcript: storeTranscript } }));
    }
  }

  return (
    <section aria-labelledby="e-counseling-media-controls-heading" className="min-w-0 border-t border-border pt-5">
      <h2 id="e-counseling-media-controls-heading" className="font-heading text-lg font-semibold text-ink">Media controls</h2>
      <p className="mt-2 text-sm leading-6 text-muted">Consent and provider capture are separate. Starting either option requires an explicit Counselor action after effective consent.</p>
      {access.canManageMediaAssigned ? consentQuery.isPending ? <div aria-busy="true" aria-label="Loading session consent controls"><Skeleton className="mt-4 h-28 w-full" /></div> : consentQuery.isError ? <div role="alert" className="mt-4 border-y border-danger/30 py-4"><p className="text-sm text-danger">Consent state could not be loaded. New requests and starts are unavailable; an active capture can still be stopped.</p><Button className="mt-3" variant="secondary" onClick={() => void consentQuery.refetch()}>Retry consent state</Button></div> : null : <p className="mt-4 border-y border-border py-4 text-sm text-muted">Media controls and assigned consent details are not available in your current access.</p>}
      <section aria-labelledby="counselor-session-media-status-heading" className="mt-4 border-y border-border py-4">
        <h3 id="counselor-session-media-status-heading" className="text-sm font-semibold text-ink">Session media activity</h3>
        <dl className="mt-2 grid gap-3 sm:grid-cols-2"><div><dt className="text-xs font-semibold text-muted">Recording</dt><dd className="mt-1 text-sm text-ink">{captureStatusLabel(workspace.media.recording.capture_status)}</dd></div><div><dt className="text-xs font-semibold text-muted">Transcription</dt><dd className="mt-1 text-sm text-ink">{captureStatusLabel(workspace.media.transcription.capture_status)}</dd></div></dl>
        {recordingStatus === "ACTIVE" ? <p role="status" className="mt-3 border-l-2 border-warning pl-3 text-sm font-semibold text-ink">Recording active</p> : null}
        {transcriptionStatus === "ACTIVE" ? <p role="status" className="mt-2 border-l-2 border-info pl-3 text-sm font-semibold text-ink">Session transcription active</p> : null}
      </section>
      {access.canManageMediaAssigned ? <div className="mt-4 grid gap-5 lg:grid-cols-2">
        <section className="min-w-0 border-y border-border py-4" aria-labelledby="recording-controls-heading">
          <h3 id="recording-controls-heading" className="font-semibold text-ink">Audio/video recording</h3>
          <dl className="mt-3 space-y-3"><div><dt className="text-xs font-semibold text-muted">Consent</dt><dd className="mt-1 text-sm text-ink">{canReadConsents ? consentRowsLabel(rows, ECounselingScope.recording) : projectedConsentLabel(workspace.media.recording.consent_status)}</dd></div><div><dt className="text-xs font-semibold text-muted">Capture</dt><dd className="mt-1 text-sm text-ink">{captureStatusLabel(recordingStatus)}</dd></div></dl>
          {recordingStatus === "ACTIVE" ? <p role="status" className="mt-3 border-l-2 border-warning pl-3 text-sm font-semibold text-ink">Recording active</p> : null}
          <div className="mt-4 flex flex-wrap gap-2">
            {canReadConsents && noRecordingRequest ? <Button variant="secondary" disabled={busy} onClick={() => void requestConsent([ECounselingScope.recording])}>Request recording consent</Button> : null}
            {recordingCanStart ? <Button disabled={busy} onClick={() => setPendingStart("recording")}>Start recording</Button> : null}
            {recordingCanStop ? <Button variant="secondary" disabled={busy} onClick={() => void runCommand(() => stopRecording.mutateAsync({ appointmentId }))}>Stop recording</Button> : null}
            {!recordingCanStart && recordingStatus === "NOT_STARTED" && !recordingApproved ? <p className="basis-full text-sm text-muted">Recording can start only after the Student’s recording consent is effective.</p> : null}
            {recordingStatus === "READY" ? <p role="status" className="basis-full text-sm text-muted">Recording completed.</p> : null}
          </div>
        </section>
        <section className="min-w-0 border-y border-border py-4" aria-labelledby="transcription-controls-heading">
          <h3 id="transcription-controls-heading" className="font-semibold text-ink">Session transcription</h3>
          <dl className="mt-3 space-y-3"><div><dt className="text-xs font-semibold text-muted">Consent</dt><dd className="mt-1 text-sm text-ink">{canReadConsents ? consentRowsLabel(rows, ECounselingScope.transcription) : projectedConsentLabel(workspace.media.transcription.consent_status)}</dd></div><div><dt className="text-xs font-semibold text-muted">Transcript storage consent</dt><dd className="mt-1 text-sm text-ink">{canReadConsents ? consentRowsLabel(rows, ECounselingScope.storage) : projectedConsentLabel(workspace.media.transcription.storage_consent_status)}</dd></div><div><dt className="text-xs font-semibold text-muted">Capture</dt><dd className="mt-1 text-sm text-ink">{captureStatusLabel(transcriptionStatus)}</dd></div><div><dt className="text-xs font-semibold text-muted">Storage</dt><dd className="mt-1 text-sm text-ink">{workspace.media.transcription.storage_enabled ? "Enabled for this capture" : "Not enabled"}</dd></div></dl>
          {transcriptionStatus === "ACTIVE" ? <p role="status" className="mt-3 border-l-2 border-info pl-3 text-sm font-semibold text-ink">Session transcription active</p> : null}
          <div className="mt-4 flex flex-wrap gap-2">
            {canReadConsents && noTranscriptionRequest ? <><Button variant="secondary" disabled={busy} onClick={() => void requestConsent([ECounselingScope.transcription])}>Request transcription consent</Button>{noStorageRequest ? <Button variant="secondary" disabled={busy} onClick={() => void requestConsent([ECounselingScope.transcription, ECounselingScope.storage])}>Request transcription + storage consent</Button> : null}</> : null}
            {canReadConsents && hasLiveTranscriptionRequest && noStorageRequest ? <Button variant="secondary" disabled={busy} onClick={() => void requestConsent([ECounselingScope.storage])}>Request transcript-storage consent</Button> : null}
            {transcriptionCanStart ? <Button disabled={busy} onClick={() => setPendingStart("transcription")}>Start transcription</Button> : null}
            {transcriptionCanStop ? <Button variant="secondary" disabled={busy} onClick={() => void runCommand(() => stopTranscription.mutateAsync({ appointmentId }))}>Stop transcription</Button> : null}
            {!transcriptionCanStart && transcriptionStatus === "NOT_STARTED" && !transcriptionApproved ? <p className="basis-full text-sm text-muted">Transcription can start only after the Student’s transcription consent is effective.</p> : null}
            {transcriptionApproved && !storageApproved && transcriptionStatus === "NOT_STARTED" ? <p className="basis-full text-sm text-muted">Transcription may run without storage consent. Transcript storage is optional.</p> : null}
            {transcriptionStatus === "READY" ? <p role="status" className="basis-full text-sm text-muted">Transcription completed. Transcript text and playback are not available in COMPASS.</p> : null}
          </div>
          {transcriptionCanStart && storageApproved && transcriptionStatus === "NOT_STARTED" ? <div className="mt-4 flex items-start gap-3 border-t border-border pt-4"><input id="e-counseling-store-transcript" type="checkbox" checked={storeTranscript} disabled={busy} onChange={(event) => setStoreTranscript(event.target.checked)} className="mt-1 size-4 rounded border border-border accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" /><div><Label htmlFor="e-counseling-store-transcript">Store transcript for this session</Label><p className="mt-1 text-sm text-muted">Optional and off by default. This choice must be made before transcription starts.</p></div></div> : null}
        </section>
      </div> : null}
      {error ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
      {notice ? <p role="status" className="mt-4 text-sm text-success">{notice}</p> : null}
      {!workspace.provider_readiness.daily_enabled ? <p className="mt-4 border-y border-border py-4 text-sm text-muted">Daily provider media controls are not enabled. Counseling access is unaffected.</p> : null}
      {workspace.provider_readiness.daily_enabled && (!workspace.provider_readiness.room_provisioned || !workspace.provider_readiness.join_allowed) ? <p className="mt-4 text-sm text-muted">Provider controls are unavailable until the session is ready.</p> : null}
      <AlertDialog open={Boolean(pendingStart)} onOpenChange={(open) => { if (!open && !busy) setPendingStart(null); }}>
        {pendingStart ? <AlertDialogContent>
          <AlertDialogTitle>{pendingStart === "recording" ? "Start audio/video recording?" : "Start session transcription?"}</AlertDialogTitle>
          <AlertDialogDescription>{pendingStart === "recording" ? "Recording will start only because the Student has currently approved this session’s recording consent." : storeTranscript ? "Speech will be processed as text while transcription is active. Transcript storage is enabled for this transcription because the Student has approved both transcription and transcript storage. COMPASS does not display or provide transcript text." : "Speech will be processed as text while transcription is active. COMPASS does not display or provide transcript text."}</AlertDialogDescription>
          <div className="mt-6 flex justify-end gap-2"><AlertDialogCancel asChild><Button variant="secondary" disabled={busy}>Cancel</Button></AlertDialogCancel><AlertDialogAction asChild><Button disabled={busy} onClick={(event) => { event.preventDefault(); void confirmStartAction(); }}>{busy ? "Starting…" : pendingStart === "recording" ? "Start recording" : "Start transcription"}</Button></AlertDialogAction></div>
        </AlertDialogContent> : null}
      </AlertDialog>
    </section>
  );
}
