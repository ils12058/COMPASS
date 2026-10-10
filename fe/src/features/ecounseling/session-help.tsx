"use client";

import type { MediaPolicyVersion } from "@/lib/api/generated/model";
import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

const callAndDevices: HelpSection = {
  heading: "Call and devices",
  content: "Use Devices to choose a camera, microphone or, where your browser allows it, a speaker. If the browser blocks your camera or microphone, allow access in its site settings, then rejoin. You can leave and rejoin while the session is open; leaving doesn’t complete the Appointment, and it doesn’t stop recording or transcription.",
};

const encounterRecords: HelpSection = {
  heading: "Encounter records",
  content: "Recording a Counseling Encounter documents that counseling took place. It is separate from recording audio or video and from completing the Appointment.",
};

export const ecounselingHelpSections: readonly HelpSection[] = [
  { heading: "Media consent", content: "The student decides separately whether audio/video recording, live transcription, and transcript storage are allowed. Declining or withdrawing consent doesn’t affect access to Counseling." },
  { heading: "Recording", content: "Captures audio and video while recording is on. Consent approval alone doesn’t start recording; the Counselor starts and stops it from the call controls. Active and stopping states stay visible on the call." },
  { heading: "Transcription", content: "Processes speech as text while transcription is on. Transcript text isn’t shown during the session, and transcription can run without transcript storage." },
  { heading: "Transcript storage", content: "Optional, off by default, and requires separate student consent before transcription starts. Transcript text, playback, and recording downloads aren’t available for these sessions." },
  encounterRecords,
  callAndDevices,
];

export const ecounselingV2HelpSections: readonly HelpSection[] = [
  { heading: "Media permission", content: "One student decision allows recording and live transcription for this session; saving a transcript needs a separate decision. Allowing never starts either one. Declining or withdrawing doesn’t affect access to Counseling." },
  { heading: "Recording", content: "The Counselor starts and stops recording from the call controls after reviewing what it does. A completed recording is prepared for private storage before it can be downloaded by the assigned Counselor." },
  { heading: "Live transcription and saved transcripts", content: "Live transcription processes speech as text while it’s on; transcript text isn’t shown during the session. A transcript file is saved only when the student allowed transcript storage and the Counselor chose to save it before starting." },
  { heading: "Private files", content: "Completed files appear under Session files once they’re prepared. Each download creates a short-lived link. Withdrawing permission stops affected capture; files already captured remain subject to institutional retention rules and holds. Downloaded copies can’t be recalled." },
  encounterRecords,
  callAndDevices,
];

export function ECounselingHelp({ mediaPolicyVersion }: { mediaPolicyVersion?: MediaPolicyVersion }) {
  return <ContextHelp title="About E-Counseling" sections={mediaPolicyVersion === 2 ? ecounselingV2HelpSections : ecounselingHelpSections} />;
}
