"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const institutionalFormsHelpSections: readonly HelpSection[] = [
  { heading: "Controlled documents", content: "This reference lists controlled forms recognized by COMPASS, rather than every questionnaire, workflow, report, or PDF." },
  { heading: "Official code and revision", content: "These are the official form codes. Current means the revision used for new records." },
  { heading: "Works with COMPASS", content: "Supported means COMPASS can use that revision. Changes to a form need a COMPASS update." },
  { heading: "Historical identity and branding", content: "Some official revisions keep their former CNSC/GTA codes. UCN branding doesn't change those form codes." },
];

export function InstitutionalFormsHelp() {
  return <ContextHelp title="About institutional forms" sections={institutionalFormsHelpSections} />;
}
