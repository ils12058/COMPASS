"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const referralHelpSections: readonly HelpSection[] = [
  { heading: "Referral details", content: "The name and course written on the referral are preserved alongside the student's current account. Referred date and received date describe different events." },
  { heading: "Recorded actions", content: "Entries document actions already taken. Recording an action does not place a call, send a letter, or notify the student." },
  { heading: "Linked Call Slips", content: "Issuing a linked Call Slip also records the Referral action if needed. An existing action is reused. Recording an action only does not issue a digital Call Slip or notify the student." },
  { heading: "Voiding", content: "A voided Referral remains available for review. New actions, status-note changes, and linked issuance stop. An active linked Call Slip must be voided first; a completed interview prevents Referral voiding." },
];

export function ReferralHelp() {
  return <ContextHelp title="About Referrals" sections={referralHelpSections} />;
}
