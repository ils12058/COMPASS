"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const institutionalFormsHelpSections: readonly HelpSection[] = [
  { heading: "Controlled documents", content: "This reference lists controlled forms recognized by COMPASS, rather than every questionnaire, workflow, report, or PDF." },
  { heading: "Official code and revision", content: "These identify the institutional controlled document. Current means the revision selected for new records." },
  { heading: "COMPASS support", content: "Supported means the deployed software understands that exact revision. It does not grant institutional approval. Support is updated with the deployed version after confirmed form changes." },
  { heading: "Historical identity and branding", content: "Some confirmed revisions retain former CNSC/GTA codes. Current UCN branding does not rewrite those controlled-document identities." },
];

export function InstitutionalFormsHelp() {
  return <ContextHelp title="About Institutional Forms" sections={institutionalFormsHelpSections} />;
}
