import { ECounselingCaptureStatus, type MediaWorkspaceState } from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";
import { captureSafetyState } from "../runtime/runtime-model";

type Indicator = { key: string; label: string; recording: boolean };

const recordingLabels: Partial<Record<ECounselingCaptureStatus, string>> = {
  [ECounselingCaptureStatus.START_REQUESTED]: "Recording starting…",
  [ECounselingCaptureStatus.ACTIVE]: "Recording",
  [ECounselingCaptureStatus.STOP_REQUESTED]: "Recording stopping…",
  [ECounselingCaptureStatus.ERROR]: "Recording status uncertain",
};

const transcriptionLabels: Partial<Record<ECounselingCaptureStatus, string>> = {
  [ECounselingCaptureStatus.START_REQUESTED]: "Transcription starting…",
  [ECounselingCaptureStatus.ACTIVE]: "Transcription on",
  [ECounselingCaptureStatus.STOP_REQUESTED]: "Transcription stopping…",
  [ECounselingCaptureStatus.ERROR]: "Transcription status uncertain",
  [ECounselingCaptureStatus.STOPPED]: "Transcription stop not confirmed",
};

// What is being captured right now, from the COMPASS session state only: never from consent alone
// and never from a provider event in the browser. Shown on the call stage for both people.
export function captureIndicators(media: MediaWorkspaceState | undefined): Indicator[] {
  const indicators: Indicator[] = [];
  if (!media) return indicators;
  const recording = captureSafetyState("recording", media.recording.capture_status) === "terminal" ? undefined : recordingLabels[media.recording.capture_status];
  const transcription = captureSafetyState("transcription", media.transcription.capture_status) === "terminal" ? undefined : transcriptionLabels[media.transcription.capture_status];
  if (recording) indicators.push({ key: "recording", label: recording, recording: media.recording.capture_status === ECounselingCaptureStatus.ACTIVE });
  if (transcription) indicators.push({ key: "transcription", label: transcription, recording: false });
  return indicators;
}

// The live region is always present, so a capture starting or stopping is announced.
export function CaptureIndicators({ media, className }: { media: MediaWorkspaceState | undefined; className?: string }) {
  const indicators = captureIndicators(media);
  return (
    <div aria-live="polite" className={className}>
      {indicators.length ? (
        <ul aria-label="Session capture" className="flex flex-col items-start gap-1">
          {indicators.map((indicator) => (
            <li key={indicator.key} className="inline-flex items-center gap-1.5 rounded-sm bg-ink/85 px-2 py-1 text-xs font-semibold text-on-brand">
              <span aria-hidden="true" className={cn("size-2 rounded-full", indicator.recording ? "bg-danger ring-2 ring-on-brand/70" : "bg-on-brand/80")} />
              {indicator.label}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
