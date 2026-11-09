"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const retentionHelpSections: readonly HelpSection[] = [
  { heading: "Where policies come from", content: "Policy changes need University approval and a reviewed COMPASS update." },
  { heading: "Your role", content: "You can review the recorded status here. Retention periods, policy references, and effective dates can’t be created or edited in COMPASS." },
  { heading: "Records disposition", content: "COMPASS doesn’t schedule, approve or carry out deletion or anonymization under these policies. Follow the University’s records disposition process outside COMPASS." },
];

export function RetentionHelp() {
  return <ContextHelp title="About retention policies" sections={retentionHelpSections} />;
}
