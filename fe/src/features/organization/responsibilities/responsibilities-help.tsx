"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const responsibilitiesHelpSections: readonly HelpSection[] = [
  { heading: "Default routing", content: "One responsible Counselor may be assigned to each College. When none is assigned, routing uses the Head Guidance Counselor only when exactly one active Head Guidance Counselor can be identified." },
  { heading: "Confidential records", content: "A Counselor's College assignments determine where new work goes. These assignments don't grant access to every confidential record." },
  { heading: "Staff supervision", content: "Guidance Office Assistants handle their supervisor's assigned Colleges, including Colleges routed to the Head Guidance Counselor when no valid Counselor is assigned. They do not gain the Head Guidance Counselor's oversight permissions; changing or removing a supervisor changes the Colleges they handle." },
];

export function ResponsibilitiesHelp() {
  return <ContextHelp title="About responsibilities" sections={responsibilitiesHelpSections} />;
}
