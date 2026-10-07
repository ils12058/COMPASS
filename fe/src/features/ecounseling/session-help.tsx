"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const ecounselingHelpSections: readonly HelpSection[] = [
  { heading: "Media consent", content: "The student decides separately whether audio/video recording, live transcription, and transcript storage are allowed. Declining or withdrawing consent does not affect access to Counseling." },
  { heading: "Recording", content: "Captures audio and video while recording is active. Consent approval alone does not start recording. Active and stopping states stay visible beside the session." },
  { heading: "Transcription", content: "Processes speech as text while transcription is active. It can run without transcript storage." },
  { heading: "Transcript storage", content: "Optional, off by default, and requires separate student consent before transcription starts. Transcript text, playback, and recording downloads are not available here." },
  { heading: "Encounter records", content: "Recording a Counseling Encounter documents a completed interaction. It is separate from recording audio/video and from completing the Appointment." },
];

export function ECounselingHelp() {
  return <ContextHelp title="About E-Counseling" sections={ecounselingHelpSections} />;
}
