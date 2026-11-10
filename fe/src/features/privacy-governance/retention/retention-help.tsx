"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const retentionHelpSections: readonly HelpSection[] = [
  { heading: "Where policies come from", content: "Retention periods follow the University’s records retention schedule." },
  { heading: "Your role", content: "You can review the recorded status here. Retention periods, policy references, and effective dates can’t be created or edited in COMPASS." },
  { heading: "Records disposition", content: "COMPASS doesn’t schedule, approve or carry out deletion or anonymization under these policies. Follow the University’s records disposition process outside COMPASS." },
];

export function RetentionHelp() {
  return <ContextHelp title="About retention policies" sections={retentionHelpSections} />;
}
