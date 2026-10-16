"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const retentionHelpSections: readonly HelpSection[] = [
  { heading: "Where policies come from", content: "Retention policy definitions are maintained in version-controlled COMPASS code. A definition changes only after the University approves the policy and the change is reviewed and released." },
  { heading: "Your role", content: "You can review the recorded status here. Retention periods, policy references, and effective dates can’t be created or edited in COMPASS." },
  { heading: "Records disposition", content: "COMPASS doesn’t schedule, approve, or carry out deletion or anonymization under these policies. Formal records disposition goes through the University’s authorized process outside COMPASS." },
];

export function RetentionHelp() {
  return <ContextHelp title="About Retention Policies" sections={retentionHelpSections} />;
}
