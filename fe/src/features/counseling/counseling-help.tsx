"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const counselingHelpSections: readonly HelpSection[] = [
  { heading: "Student information", content: "Tabs show information available for this interaction. Student Intake remains private until submission. Access can expire, and permissions are checked again when information is loaded." },
  { heading: "Encounter", content: "A Counseling Encounter records the actual start and end of a completed interaction. Recording it does not complete an Appointment and does not start audio/video recording." },
  { heading: "Routine Interview", content: "When an encounter is recorded from a Routine Interview workspace, it is linked to that interview. An encounter recorded elsewhere can be selected when finalizing the evaluation." },
  { heading: "Shared summaries", content: "A summary draft stays private to its counselor until publication. Publishing makes it visible to the student and locks ordinary editing." },
];

export function CounselingHelp() {
  return <ContextHelp title="About Counseling" sections={counselingHelpSections} />;
}
