"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const counselingHelpSections: readonly HelpSection[] = [
  { heading: "Student information", content: "Student Intake stays private until submission. Access can expire, so your access is checked whenever you load information." },
  { heading: "Encounter", content: "A Counseling Encounter records when a completed conversation started and ended. Recording it keeps the Appointment status unchanged and does not start audio/video recording." },
  { heading: "Routine Interview", content: "When an encounter is recorded from a Routine Interview workspace, it is linked to that interview. An encounter recorded elsewhere can be selected when finalizing the evaluation." },
  { heading: "Student Session Summaries", content: "A summary draft stays private to its Counselor until publication. Publishing makes it visible to the Student and locks ordinary editing." },
];

export function CounselingHelp() {
  return <ContextHelp title="About Counseling" sections={counselingHelpSections} />;
}
