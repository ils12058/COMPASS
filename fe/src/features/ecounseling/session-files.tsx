"use client";

import { DisclosureSection } from "@/components/ui/disclosure";
import { ECounselingCaptureStatus, type ECounselingMediaKind, type MediaWorkspaceState, type RecordingWorkspaceState, type TranscriptionWorkspaceState } from "@/lib/api/generated/model";

import { MediaArtifactDownload, artifactOutcome } from "./media-artifact-download";

type Outcome = { text: string; short: string };
type FileRow = { kind: ECounselingMediaKind; label: string; outcome: Outcome; state: RecordingWorkspaceState | TranscriptionWorkspaceState };

const ended: ReadonlySet<ECounselingCaptureStatus> = new Set([ECounselingCaptureStatus.STOPPED, ECounselingCaptureStatus.READY]);
const running: ReadonlySet<ECounselingCaptureStatus> = new Set([
  ECounselingCaptureStatus.START_REQUESTED,
  ECounselingCaptureStatus.ACTIVE,
  ECounselingCaptureStatus.STOP_REQUESTED,
]);
const deleted: Outcome = { text: "Deleted under an approved retention rule.", short: "deleted" };

function recordingOutcome(media: MediaWorkspaceState): Outcome | null {
  const recording = media.recording;
  if (media.media_policy_version !== 2) {
    if (recording.artifact_disposed_at) return deleted;
    return recording.capture_status === ECounselingCaptureStatus.READY ? { text: "Recording completed.", short: "completed" } : null;
  }
  const file = artifactOutcome("RECORDING", recording);
  if (file) return file;
  if (running.has(recording.capture_status)) return { text: "Available after recording ends.", short: "in progress" };
  if (ended.has(recording.capture_status)) return { text: "Preparing file…", short: "preparing" };
  return null;
}

function transcriptOutcome(media: MediaWorkspaceState): Outcome | null {
  const transcription = media.transcription;
  if (media.media_policy_version !== 2) {
    if (transcription.artifact_disposed_at) return deleted;
    if (transcription.capture_status === ECounselingCaptureStatus.READY) return { text: "Transcription completed. The transcript was stored by the video service.", short: "completed" };
    return transcription.capture_status === ECounselingCaptureStatus.STOPPED ? { text: "Transcription completed. No transcript was stored.", short: "not stored" } : null;
  }
  const file = artifactOutcome("TRANSCRIPTION", transcription);
  if (file) return file;
  if (!ended.has(transcription.capture_status)) return null;
  // Live transcription without saving ends without a file; that is the outcome to state, not a
  // storage setting.
  return transcription.storage_enabled ? { text: "Preparing file…", short: "preparing" } : { text: "No transcript saved.", short: "not saved" };
}

// What each capture produced, described by its outcome. V2 sessions have COMPASS-held files; V1
// sessions kept files with the video service, so they show completion only.
export function sessionFileRows(media: MediaWorkspaceState): FileRow[] {
  const rows: FileRow[] = [];
  const recording = recordingOutcome(media);
  const transcript = transcriptOutcome(media);
  if (recording) rows.push({ kind: "RECORDING", label: "Recording", outcome: recording, state: media.recording });
  if (transcript) rows.push({ kind: "TRANSCRIPTION", label: "Transcript", outcome: transcript, state: media.transcription });
  return rows;
}

// Completed recordings and transcripts, kept out of the live call controls. Each download asks for
// a fresh link on click (MediaArtifactDownload).
export function SessionFiles({
  appointmentId,
  media,
  canAccess,
  defaultOpen,
}: {
  appointmentId: string;
  media: MediaWorkspaceState;
  canAccess: boolean;
  defaultOpen: boolean;
}) {
  const rows = sessionFileRows(media);
  if (!rows.length) return null;
  const summary = rows.map((row) => `${row.label} ${row.outcome.short}`).join(" · ");
  return (
    <DisclosureSection title="Session files" status={summary.charAt(0).toUpperCase() + summary.slice(1)} defaultOpen={defaultOpen}>
      <ul className="divide-y divide-border">
        {rows.map((row) => (
          <li key={row.kind} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-1 py-3">
            <div className="min-w-0">
              <p className="font-semibold text-ink">{row.label}</p>
              <p className="text-sm text-muted">{row.outcome.text}</p>
            </div>
            {media.media_policy_version === 2 ? <MediaArtifactDownload appointmentId={appointmentId} kind={row.kind} state={row.state} canAccess={canAccess} /> : null}
          </li>
        ))}
      </ul>
    </DisclosureSection>
  );
}
