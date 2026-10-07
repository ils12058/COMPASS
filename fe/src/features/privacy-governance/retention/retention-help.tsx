"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const retentionHelpSections: readonly HelpSection[] = [
  { heading: "Institutional policy", content: "Use an approved policy reference and duration. No default retention period is supplied. Drafting a rule does not authorize disposition." },
  { heading: "Eligibility and approval", content: "An active rule identifies eligible records. Eligibility alone never authorizes disposition; each approval applies to one fixed record reviewed in its current state." },
  { heading: "Holds and retries", content: "Active holds block disposition. A failed case requires a fresh review and explicit retry authorization. Consequences remain visible in the approval dialog." },
];

export function RetentionHelp() {
  return <ContextHelp title="About Retention and disposition" sections={retentionHelpSections} />;
}
