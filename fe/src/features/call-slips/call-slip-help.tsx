"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const callSlipHelpSections: readonly HelpSection[] = [
  { heading: "Permit", content: "The student shows the Call Slip to their instructor and reports to the destination written on it. Names and course details on the issued permit are preserved separately from current account details." },
  { heading: "Interview end", content: "Record when the interview ended. This time cannot be edited once saved. It does not complete a related Appointment or Counseling record." },
  { heading: "Issuance and withdrawal", content: "The issuance choice determines whether the student receives a notification. The withdrawal dialog states whether the student will be notified. Voiding preserves the historical record." },
];

export function CallSlipHelp() {
  return <ContextHelp title="About Call Slips" sections={callSlipHelpSections} />;
}
