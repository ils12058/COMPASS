"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

// E-Counseling is recording-only: there is no transcription, transcript or captions feature.
export const ecounselingHelpSections: readonly HelpSection[] = [
  {
    heading: "Recording permission",
    content: "Recording is optional. If the Student agrees, the Counselor may start an audio/video recording of this session. The Student may withdraw permission during the session, and COMPASS then asks the recording to stop. Declining or withdrawing doesn’t affect access to Counseling.",
  },
  {
    heading: "Recording",
    content: "The Counselor starts and stops recording from the call controls. Allowing permission never starts it. Active and stopping states stay visible on the call.",
  },
  {
    heading: "Private files",
    content: "A completed recording is prepared for private storage and appears under Session files. Only the assigned Counselor can download it, and each download creates a short-lived link. Withdrawing permission doesn’t delete what was already recorded; it stays subject to the University’s records and privacy requirements. Downloaded copies can’t be recalled.",
  },
  {
    heading: "Encounter records",
    content: "Recording audio or video doesn’t document the session. Finishing counseling records the Counseling Encounter and completes the Appointment in one action, once the online access period has ended.",
  },
  {
    heading: "Call and devices",
    content: "Use Check devices before joining to test your camera, microphone, and speaker on your device, or use Devices during a call to switch them. If the browser blocks your camera or microphone, allow access in its site settings, then rejoin. You can leave and rejoin while the session is open. Leaving doesn’t complete the Appointment or stop recording.",
  },
];

export function ECounselingHelp() {
  return <ContextHelp title="About E-Counseling" sections={ecounselingHelpSections} />;
}
