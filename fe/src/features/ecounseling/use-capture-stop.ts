"use client";

import { useState } from "react";

import { ecounselingErrorMessage } from "@/features/ecounseling/ecounseling-shared";
import { settleCaptureStop } from "@/features/ecounseling/runtime/runtime-model";
import {
  useECounselingStopAssignedRecording,
  useECounselingStopAssignedTranscription,
} from "@/lib/api/generated/e-counseling/e-counseling";

export type CaptureKind = "recording" | "transcription";

// The assigned Counselor's protective stop for a running recording or transcription, used by the
// session page and by the call dock on any portal page. It always goes through the COMPASS backend
// (ADR-092); the browser's call object never stops capture. `onSettled` refreshes the session, which
// then decides what is shown, so "Stopping…" holds until COMPASS confirms the change. A Stop request
// that failed is kept as `failed` so the control says the stop is not confirmed instead of "Stopping…".
export function useCaptureStop(appointmentId: string | null, onSettled: () => Promise<unknown> | void) {
  const stopRecording = useECounselingStopAssignedRecording({ mutation: { retry: false } });
  const stopTranscription = useECounselingStopAssignedTranscription({ mutation: { retry: false } });
  const [stopping, setStopping] = useState<Record<CaptureKind, boolean>>({ recording: false, transcription: false });
  const [failed, setFailed] = useState<Record<CaptureKind, boolean>>({ recording: false, transcription: false });
  const [error, setError] = useState<string | null>(null);

  async function stop(kind: CaptureKind) {
    if (!appointmentId) return;
    setError(null);
    setFailed((current) => ({ ...current, [kind]: false }));
    setStopping((current) => ({ ...current, [kind]: true }));
    try {
      await settleCaptureStop(
        () => kind === "recording" ? stopRecording.mutateAsync({ appointmentId }) : stopTranscription.mutateAsync({ appointmentId }),
        onSettled,
        (caught) => {
          setFailed((current) => ({ ...current, [kind]: true }));
          setError(ecounselingErrorMessage(caught, kind === "recording"
            ? "Recording couldn’t be stopped. Try again."
            : "Transcription couldn’t be stopped. Try again."));
        },
      );
    } finally {
      setStopping((current) => ({ ...current, [kind]: false }));
    }
  }

  return { stopping, failed, error, clearError: () => setError(null), stop };
}
