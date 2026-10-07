"use client";

import type { MediaPolicyVersion } from "@/lib/api/generated/model";
import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const ecounselingHelpSections: readonly HelpSection[] = [
  { heading: "Media consent", content: "The student decides separately whether audio/video recording, live transcription, and transcript storage are allowed. Declining or withdrawing consent does not affect access to Counseling." },
  { heading: "Recording", content: "Captures audio and video while recording is active. Consent approval alone does not start recording. Active and stopping states stay visible beside the session." },
  { heading: "Transcription", content: "Processes speech as text while transcription is active. It can run without transcript storage." },
  { heading: "Transcript storage", content: "Optional, off by default, and requires separate student consent before transcription starts. Transcript text, playback, and recording downloads are not available here." },
  { heading: "Encounter records", content: "Recording a Counseling Encounter documents a completed interaction. It is separate from recording audio/video and from completing the Appointment." },
];

export const ecounselingV2HelpSections: readonly HelpSection[] = [
  { heading: "Media consent", content: "One student decision permits recording and live transcription. Transcript storage requires a separate decision. Approval alone never starts capture. Declining or withdrawing does not affect Counseling access." },
  { heading: "Recording", content: "The Counselor starts recording separately. Completed recordings are prepared for private storage before a download becomes available to the assigned Counselor." },
  { heading: "Transcript storage", content: "Live transcription can run without saving a file. Saving is off by default and requires both media consent and transcript storage consent before transcription starts." },
  { heading: "Private files", content: "Preparing a file is separate from completing capture. Download actions create short-lived access links. Withdrawing consent stops affected capture; files already captured remain subject to institutional retention rules and holds. Downloaded copies cannot be recalled." },
  { heading: "Encounter records", content: "A Counseling Encounter documents a completed interaction. It remains separate from media capture and Appointment completion." },
];

export function ECounselingHelp({ mediaPolicyVersion }: { mediaPolicyVersion?: MediaPolicyVersion }) {
  return <ContextHelp title="About E-Counseling" sections={mediaPolicyVersion === 2 ? ecounselingV2HelpSections : ecounselingHelpSections} />;
}
